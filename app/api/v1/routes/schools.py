"""School routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.core.permissions import Role
from app.schemas.school import (
    SchoolCreate,
    SchoolListResponse,
    SchoolResponse,
    SchoolSubscriptionUpdate,
    SchoolUpdate,
)
from app.services import school as school_service

router = APIRouter(prefix="/schools", tags=["Schools"])


# ============== Endpoints ==============


@router.get("", response_model=SchoolListResponse)
async def list_schools(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Search by school name"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of records"),
) -> SchoolListResponse:
    """
    List schools.

    - OWNER/SUPERUSER: Can see all schools
    - Others: Can only see their own school
    """
    if current_user.is_superuser:
        schools, total = await school_service.get_schools(
            db,
            is_active=is_active,
            search=search,
            skip=skip,
            limit=limit,
        )
    else:
        # Non-superusers can only see their own school
        if current_user.school_id:
            school = await school_service.get_school_by_id(db, current_user.school_id)
            schools = [school] if school else []
            total = 1 if school else 0
        else:
            schools = []
            total = 0

    return SchoolListResponse(
        items=[SchoolResponse.model_validate(s) for s in schools],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=SchoolResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Role.OWNER, Role.SUPERUSER))],
)
async def create_school(
    school_data: SchoolCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SchoolResponse:
    """
    Create a new school.

    - Only OWNER and SUPERUSER can create schools
    """
    school = await school_service.create_school(db, school_data)
    return SchoolResponse.model_validate(school)


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SchoolResponse:
    """
    Get a specific school by ID.

    - OWNER/SUPERUSER: Can see any school
    - Others: Can only see their own school
    """
    school = await school_service.get_school_by_id(db, school_id)

    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Non-superusers can only see their own school
    if not current_user.is_superuser and current_user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    return SchoolResponse.model_validate(school)


@router.patch(
    "/{school_id}",
    response_model=SchoolResponse,
    dependencies=[Depends(require_roles(Role.OWNER, Role.SUPERUSER))],
)
async def update_school(
    school_id: UUID,
    school_data: SchoolUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SchoolResponse:
    """
    Update a school.

    - Only OWNER and SUPERUSER can update schools
    """
    school = await school_service.get_school_by_id(db, school_id)

    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    updated_school = await school_service.update_school(db, school, school_data)
    return SchoolResponse.model_validate(updated_school)


@router.patch(
    "/{school_id}/subscription",
    response_model=SchoolResponse,
    dependencies=[Depends(require_roles(Role.OWNER, Role.SUPERUSER))],
)
async def update_school_subscription(
    school_id: UUID,
    subscription_data: SchoolSubscriptionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SchoolResponse:
    """
    Update school subscription dates.

    - Only OWNER and SUPERUSER can manage subscriptions
    """
    school = await school_service.get_school_by_id(db, school_id)

    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    updated_school = await school_service.update_subscription(
        db, school, subscription_data
    )
    return SchoolResponse.model_validate(updated_school)


@router.delete(
    "/{school_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.OWNER, Role.SUPERUSER))],
)
async def delete_school(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Deactivate a school (soft delete).

    - Only OWNER and SUPERUSER can delete schools
    """
    school = await school_service.get_school_by_id(db, school_id)

    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    await school_service.deactivate_school(db, school)
