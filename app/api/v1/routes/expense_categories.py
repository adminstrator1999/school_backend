"""Expense Category API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.core.permissions import Role
from app.schemas.expense_category import (
    ExpenseCategoryCreate,
    ExpenseCategoryListResponse,
    ExpenseCategoryResponse,
    ExpenseCategoryUpdate,
)
from app.services import expense_category as category_service
from app.services import school as school_service

router = APIRouter(prefix="/expense-categories", tags=["Expense Categories"])


# ============== Helper Functions ==============


def can_manage_categories(user) -> bool:
    """Check if user has permission to create/update/delete expense categories."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.ACCOUNTANT,
    )


# ============== Endpoints ==============


@router.get("", response_model=ExpenseCategoryListResponse)
async def list_expense_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    search: str | None = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Max number of records"),
) -> ExpenseCategoryListResponse:
    """
    List expense categories with optional filters.

    - OWNER/SUPERUSER: Can see all categories, can filter by school_id
    - Others: Can only see categories from their school (+ system categories)
    """
    # Non-superusers can only see their own school's categories (plus system)
    if not current_user.is_superuser:
        school_id = current_user.school_id

    categories, total = await category_service.get_expense_categories(
        db,
        school_id=school_id,
        search=search,
        include_system=True,
        skip=skip,
        limit=limit,
    )

    return ExpenseCategoryListResponse(
        items=[ExpenseCategoryResponse.model_validate(c) for c in categories],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=ExpenseCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_expense_category(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    category_data: ExpenseCategoryCreate,
) -> ExpenseCategoryResponse:
    """
    Create a new expense category.

    - OWNER/SUPERUSER: Can create categories for any school
    - DIRECTOR/ACCOUNTANT: Can create categories for their school only
    """
    if not can_manage_categories(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to create expense categories",
        )

    # Non-superusers can only create for their own school
    if not current_user.is_superuser:
        if category_data.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create expense categories for other schools",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, category_data.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Check for duplicate name
    if await category_service.check_duplicate_category(
        db, category_data.school_id, category_data.name
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expense category with this name already exists",
        )

    category = await category_service.create_expense_category(db, category_data)
    return ExpenseCategoryResponse.model_validate(category)


@router.get("/{category_id}", response_model=ExpenseCategoryResponse)
async def get_expense_category(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    category_id: UUID,
) -> ExpenseCategoryResponse:
    """
    Get an expense category by ID.
    """
    # Determine school filter
    school_id = None if current_user.is_superuser else current_user.school_id

    category = await category_service.get_expense_category_by_id(
        db, category_id, school_id=school_id
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense category not found",
        )

    return ExpenseCategoryResponse.model_validate(category)


@router.patch("/{category_id}", response_model=ExpenseCategoryResponse)
async def update_expense_category(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    category_id: UUID,
    category_data: ExpenseCategoryUpdate,
) -> ExpenseCategoryResponse:
    """
    Update an expense category.

    - System categories cannot be updated
    """
    if not can_manage_categories(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update expense categories",
        )

    # Determine school filter
    school_id = None if current_user.is_superuser else current_user.school_id

    category = await category_service.get_expense_category_by_id(
        db, category_id, school_id=school_id
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense category not found",
        )

    # Cannot update system categories
    if category.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update system expense categories",
        )

    # Non-superusers can only update their own school's categories
    if not current_user.is_superuser:
        if category.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update expense categories from other schools",
            )

    # Check for duplicate name
    if category_data.name:
        if await category_service.check_duplicate_category(
            db, category.school_id, category_data.name, exclude_id=category_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Expense category with this name already exists",
            )

    category = await category_service.update_expense_category(db, category, category_data)
    return ExpenseCategoryResponse.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense_category(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    category_id: UUID,
) -> None:
    """
    Delete an expense category.

    - Only OWNER/SUPERUSER/DIRECTOR can delete
    - System categories cannot be deleted
    """
    if current_user.role not in (Role.OWNER, Role.SUPERUSER, Role.DIRECTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete expense categories",
        )

    # Determine school filter
    school_id = None if current_user.is_superuser else current_user.school_id

    category = await category_service.get_expense_category_by_id(
        db, category_id, school_id=school_id
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense category not found",
        )

    # Cannot delete system categories
    if category.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system expense categories",
        )

    # Non-superusers can only delete their own school's categories
    if not current_user.is_superuser:
        if category.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete expense categories from other schools",
            )

    try:
        await category_service.delete_expense_category(db, category)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
