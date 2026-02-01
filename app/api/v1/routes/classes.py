"""School classes API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.core.permissions import Role
from app.schemas.school_class import (
    SchoolClassCreate,
    SchoolClassListResponse,
    SchoolClassResponse,
    SchoolClassUpdate,
)
from app.services import school as school_service
from app.services import school_class as school_class_service

router = APIRouter(prefix="/classes", tags=["Classes"])


@router.get("", response_model=SchoolClassListResponse)
async def list_classes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    school_id: UUID | None = None,
    grade: int | None = Query(None, ge=1, le=11),
    is_active: bool | None = None,
):
    """List all school classes with optional filters."""
    classes, total = await school_class_service.get_school_classes(
        db, skip=skip, limit=limit, school_id=school_id, grade=grade, is_active=is_active
    )
    return SchoolClassListResponse(items=classes, total=total, skip=skip, limit=limit)


@router.post(
    "",
    response_model=SchoolClassResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_class(
    class_data: SchoolClassCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        CurrentUser, Depends(require_roles(Role.OWNER, Role.SUPERUSER, Role.DIRECTOR))
    ],
):
    """Create a new school class."""
    # Verify school exists
    school = await school_service.get_school_by_id(db, class_data.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Check for duplicate grade/section
    existing = await school_class_service.get_school_class_by_grade_section(
        db, class_data.school_id, class_data.grade, class_data.section.upper()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Class {class_data.grade}{class_data.section.upper()} already exists for this school",
        )

    return await school_class_service.create_school_class(db, class_data)


@router.get("/{class_id}", response_model=SchoolClassResponse)
async def get_class(
    class_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Get a school class by ID."""
    school_class = await school_class_service.get_school_class_by_id(db, class_id)
    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )
    return school_class


@router.patch("/{class_id}", response_model=SchoolClassResponse)
async def update_class(
    class_id: UUID,
    class_data: SchoolClassUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        CurrentUser, Depends(require_roles(Role.OWNER, Role.SUPERUSER, Role.DIRECTOR))
    ],
):
    """Update a school class."""
    school_class = await school_class_service.get_school_class_by_id(db, class_id)
    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    # If changing grade/section, check for duplicates
    new_grade = class_data.grade if class_data.grade is not None else school_class.grade
    new_section = (
        class_data.section.upper()
        if class_data.section is not None
        else school_class.section
    )

    if new_grade != school_class.grade or new_section != school_class.section:
        existing = await school_class_service.get_school_class_by_grade_section(
            db, school_class.school_id, new_grade, new_section
        )
        if existing and existing.id != class_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Class {new_grade}{new_section} already exists for this school",
            )

    return await school_class_service.update_school_class(db, school_class, class_data)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        CurrentUser, Depends(require_roles(Role.OWNER, Role.SUPERUSER, Role.DIRECTOR))
    ],
):
    """Soft delete a school class."""
    school_class = await school_class_service.get_school_class_by_id(db, class_id)
    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    await school_class_service.deactivate_school_class(db, school_class)


@router.post(
    "/promote/{school_id}",
    response_model=dict,
    summary="Promote all students to next grade",
)
async def promote_students(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        CurrentUser, Depends(require_roles(Role.OWNER, Role.SUPERUSER, Role.DIRECTOR))
    ],
):
    """
    Promote all students in a school to the next grade.
    Students in grade 11 will be graduated and deactivated.
    This should typically be run at the start of a new school year.
    """
    school = await school_service.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    result = await school_class_service.promote_students(db, school_id)
    return {
        "message": "Students promoted successfully",
        "promoted": result["promoted"],
        "graduated": result["graduated"],
    }
