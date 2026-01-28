"""User routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import Role, can_create_role
from app.core.security import verify_password
from app.schemas.user import (
    PasswordChange,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
    UserUpdateMe,
)
from app.services import user as user_service

router = APIRouter(prefix="/users", tags=["Users"])


# ============== Helper Functions ==============

def get_role_level(role: Role) -> int:
    """Get numeric level for role comparison."""
    levels = {
        Role.OWNER: 100,
        Role.SUPERUSER: 90,
        Role.DIRECTOR: 70,
        Role.SHAREHOLDER: 70,
        Role.ACCOUNTANT: 50,
        Role.STAFF: 30,
    }
    return levels.get(role, 0)


def can_manage_user(manager: "User", target: "User") -> bool:
    """Check if manager can manage (update/delete) target user."""
    # Can't manage yourself through this (use /me endpoints)
    if manager.id == target.id:
        return False
    
    # Owner can manage everyone except other owners
    if manager.role == Role.OWNER:
        return target.role != Role.OWNER
    
    # Superuser can manage everyone except owner and other superusers
    if manager.role == Role.SUPERUSER:
        return target.role not in (Role.OWNER, Role.SUPERUSER)
    
    # School-level users can only manage users in their school
    if manager.school_id != target.school_id:
        return False
    
    # Can only manage users with lower role level
    return get_role_level(manager.role) > get_role_level(target.role)


# ============== Endpoints ==============

@router.get("", response_model=UserListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    role: Role | None = Query(None, description="Filter by role"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of records"),
) -> UserListResponse:
    """
    List users with optional filters.
    
    - OWNER/SUPERUSER: Can see all users, can filter by school_id
    - Others: Can only see users from their own school
    """
    # Non-superusers can only see their own school
    if not current_user.is_superuser:
        school_id = current_user.school_id
    
    users, total = await user_service.get_users(
        db,
        school_id=school_id,
        role=role,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> UserResponse:
    """
    Create a new user.
    
    - Can only create roles allowed by ROLE_HIERARCHY
    - Non-superusers can only create users in their own school
    """
    # Check if current user can create the target role
    if not can_create_role(current_user.role, user_data.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have permission to create users with role '{user_data.role.value}'",
        )
    
    # Non-superusers can only create users in their own school
    if not current_user.is_superuser:
        if user_data.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create users in your own school",
            )
    
    # Check if phone number is taken
    existing_user = await user_service.get_user_by_phone(db, user_data.phone_number)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered",
        )
    
    user = await user_service.create_user(db, user_data)
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    """Get current user's profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdateMe,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> UserResponse:
    """Update current user's profile (name, phone, picture)."""
    # Check if new phone number is taken
    if user_data.phone_number and user_data.phone_number != current_user.phone_number:
        existing = await user_service.get_user_by_phone(db, user_data.phone_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered",
            )
    
    # Convert to UserUpdate, preserving only set fields
    user_data_dict = user_data.model_dump(exclude_unset=True)
    update_data = UserUpdate.model_validate(user_data_dict)
    
    user = await user_service.update_user(db, current_user, update_data)
    return UserResponse.model_validate(user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    password_data: PasswordChange,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    """Change current user's password."""
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    await user_service.change_password(db, current_user, password_data.new_password)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> UserResponse:
    """
    Get a specific user by ID.
    
    - OWNER/SUPERUSER: Can see any user
    - Others: Can only see users from their own school
    """
    user = await user_service.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Non-superusers can only see users from their school
    if not current_user.is_superuser and user.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> UserResponse:
    """
    Update a user.
    
    - Can only update users with lower role level
    - Cannot change role to one you can't create
    """
    user = await user_service.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not can_manage_user(current_user, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this user",
        )
    
    # If changing role, check if allowed
    if user_data.role and user_data.role != user.role:
        if not can_create_role(current_user.role, user_data.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You can't assign role '{user_data.role.value}'",
            )
    
    # Check if new phone number is taken
    if user_data.phone_number and user_data.phone_number != user.phone_number:
        existing = await user_service.get_user_by_phone(db, user_data.phone_number)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered",
            )
    
    updated_user = await user_service.update_user(db, user, user_data)
    return UserResponse.model_validate(updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    """
    Deactivate a user (soft delete).
    
    - Can only deactivate users with lower role level
    """
    user = await user_service.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not can_manage_user(current_user, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this user",
        )
    
    await user_service.deactivate_user(db, user)
