"""Student routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import Role
from app.schemas.student import (
    StudentCreate,
    StudentListResponse,
    StudentResponse,
    StudentUpdate,
)
from app.services import school as school_service
from app.services import student as student_service

router = APIRouter(prefix="/students", tags=["Students"])


# ============== Helper Functions ==============


def can_access_school(user, school_id: UUID) -> bool:
    """Check if user can access data from a specific school."""
    if user.is_superuser:
        return True
    return user.school_id == school_id


def can_write_students(user) -> bool:
    """Check if user has permission to create/update students."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.SHAREHOLDER,
        Role.ACCOUNTANT,
    )


# ============== Endpoints ==============


@router.get("", response_model=StudentListResponse)
async def list_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    school_class_id: UUID | None = Query(None, description="Filter by class ID"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    graduated: bool | None = Query(None, description="Filter by graduation status"),
    search: str | None = Query(None, description="Search by name or phone"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of records"),
) -> StudentListResponse:
    """
    List students with optional filters.

    - OWNER/SUPERUSER: Can see all students, can filter by school_id
    - Others: Can only see students from their own school
    """
    # Non-superusers can only see their own school's students
    if not current_user.is_superuser:
        school_id = current_user.school_id

    students, total = await student_service.get_students(
        db,
        school_id=school_id,
        school_class_id=school_class_id,
        is_active=is_active,
        graduated=graduated,
        search=search,
        skip=skip,
        limit=limit,
    )

    return StudentListResponse(
        items=[StudentResponse.model_validate(s) for s in students],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> StudentResponse:
    """
    Create a new student.

    - OWNER/SUPERUSER: Can create in any school
    - DIRECTOR/SHAREHOLDER/ACCOUNTANT: Can create in their own school
    """
    if not can_write_students(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create students",
        )

    # Non-superusers can only create students in their own school
    if not current_user.is_superuser:
        if student_data.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create students in your own school",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, student_data.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    student = await student_service.create_student(db, student_data)
    return StudentResponse.model_validate(student)


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> StudentResponse:
    """
    Get a specific student by ID.

    - OWNER/SUPERUSER: Can see any student
    - Others: Can only see students from their own school
    """
    student = await student_service.get_student_by_id(db, student_id)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Check access
    if not can_access_school(current_user, student.school_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    return StudentResponse.model_validate(student)


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: UUID,
    student_data: StudentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> StudentResponse:
    """
    Update a student.

    - OWNER/SUPERUSER: Can update any student
    - DIRECTOR/SHAREHOLDER/ACCOUNTANT: Can update in their own school
    """
    if not can_write_students(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update students",
        )

    student = await student_service.get_student_by_id(db, student_id)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Check access
    if not can_access_school(current_user, student.school_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    updated_student = await student_service.update_student(db, student, student_data)
    return StudentResponse.model_validate(updated_student)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    """
    Deactivate a student (soft delete).

    - OWNER/SUPERUSER: Can delete any student
    - DIRECTOR/SHAREHOLDER: Can delete in their own school
    """
    if current_user.role not in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.SHAREHOLDER,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete students",
        )

    student = await student_service.get_student_by_id(db, student_id)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Check access
    if not can_access_school(current_user, student.school_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    await student_service.deactivate_student(db, student)
