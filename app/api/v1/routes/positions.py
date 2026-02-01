"""Position API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.core.permissions import Role
from app.schemas.position import (
    PositionCreate,
    PositionListResponse,
    PositionResponse,
    PositionUpdate,
)
from app.services import position as position_service
from app.services import school as school_service

router = APIRouter(prefix="/positions", tags=["Positions"])


# ============== Helper Functions ==============


def can_manage_positions(user) -> bool:
    """Check if user has permission to create/update/delete positions."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
    )


# ============== Endpoints ==============


@router.get("", response_model=PositionListResponse)
async def list_positions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    search: str | None = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Max number of records"),
) -> PositionListResponse:
    """
    List positions with optional filters.

    - OWNER/SUPERUSER: Can see all positions, can filter by school_id
    - Others: Can only see positions from their school (+ system positions)
    """
    # Non-superusers can only see their own school's positions (plus system)
    if not current_user.is_superuser:
        school_id = current_user.school_id

    positions, total = await position_service.get_positions(
        db,
        school_id=school_id,
        search=search,
        include_system=True,
        skip=skip,
        limit=limit,
    )

    return PositionListResponse(
        items=[PositionResponse.model_validate(p) for p in positions],
        total=total,
    )


@router.post("", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
async def create_position(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    position_data: PositionCreate,
) -> PositionResponse:
    """
    Create a new position.

    - OWNER/SUPERUSER: Can create system positions (school_id=None)
    - DIRECTOR: Can create positions for their school only
    """
    if not can_manage_positions(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to create positions",
        )

    # Non-superusers can only create for their own school
    if not current_user.is_superuser:
        if position_data.school_id and position_data.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create positions for other schools",
            )
        # Force school_id for non-superusers
        position_data = PositionCreate(
            name=position_data.name,
            school_id=current_user.school_id,
            is_system=False,  # Non-superusers can't create system positions
        )

    # Only superusers can create system positions
    if position_data.is_system and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can create system positions",
        )

    # Validate school exists if school_id provided
    if position_data.school_id:
        school = await school_service.get_school_by_id(db, position_data.school_id)
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found",
            )

    position = await position_service.create_position(db, position_data)
    return PositionResponse.model_validate(position)


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    position_id: UUID,
) -> PositionResponse:
    """Get a specific position."""
    position = await position_service.get_position_by_id(db, position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    # Check access - user can access system positions or their school's positions
    if not current_user.is_superuser:
        if position.school_id and position.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access positions from other schools",
            )

    return PositionResponse.model_validate(position)


@router.patch("/{position_id}", response_model=PositionResponse)
async def update_position(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    position_id: UUID,
    position_data: PositionUpdate,
) -> PositionResponse:
    """
    Update a position.

    - Cannot update system positions unless OWNER/SUPERUSER
    - DIRECTOR can update their school's positions only
    """
    if not can_manage_positions(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update positions",
        )

    position = await position_service.get_position_by_id(db, position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    # System positions can only be updated by superusers
    if position.is_system and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update system positions",
        )

    # Non-superusers can only update their school's positions
    if not current_user.is_superuser:
        if position.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update positions from other schools",
            )

    position = await position_service.update_position(db, position, position_data)
    return PositionResponse.model_validate(position)


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    position_id: UUID,
) -> None:
    """
    Delete a position (soft delete).

    - Cannot delete system positions
    - Only OWNER/SUPERUSER/DIRECTOR can delete
    """
    if not can_manage_positions(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete positions",
        )

    position = await position_service.get_position_by_id(db, position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    # Cannot delete system positions
    if position.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system positions",
        )

    # Non-superusers can only delete their school's positions
    if not current_user.is_superuser:
        if position.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete positions from other schools",
            )

    await position_service.delete_position(db, position)
