"""Discount API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import Role
from app.models.discount import DiscountType
from app.schemas.discount import (
    DiscountCreate,
    DiscountListResponse,
    DiscountResponse,
    DiscountUpdate,
    StudentDiscountCreate,
    StudentDiscountResponse,
    StudentDiscountsResponse,
)
from app.services import discount as discount_service
from app.services import school as school_service
from app.services import student as student_service

router = APIRouter(prefix="/discounts", tags=["Discounts"])


# ============== Helper Functions ==============


def can_manage_discounts(user) -> bool:
    """Check if user has permission to manage discounts."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.SHAREHOLDER,
        Role.ACCOUNTANT,
    )


# ============== Discount Endpoints ==============


@router.get("", response_model=DiscountListResponse)
async def list_discounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    type: DiscountType | None = Query(None, description="Filter by discount type"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Max number of records"),
) -> DiscountListResponse:
    """
    List discounts with optional filters.

    - OWNER/SUPERUSER: Can see all discounts, can filter by school_id
    - Others: Can only see discounts from their own school
    """
    # Non-superusers can only see their own school's discounts
    if not current_user.is_superuser:
        school_id = current_user.school_id

    discounts, total = await discount_service.get_discounts(
        db,
        school_id=school_id,
        discount_type=type,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
    )

    return DiscountListResponse(
        items=[DiscountResponse.model_validate(d) for d in discounts],
        total=total,
    )


@router.post("", response_model=DiscountResponse, status_code=status.HTTP_201_CREATED)
async def create_discount(
    discount_data: DiscountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> DiscountResponse:
    """
    Create a new discount.

    - OWNER/SUPERUSER: Can create in any school
    - DIRECTOR/SHAREHOLDER/ACCOUNTANT: Can create in their own school
    """
    if not can_manage_discounts(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to create discounts",
        )

    # Non-superusers can only create discounts in their own school
    if not current_user.is_superuser:
        if discount_data.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create discounts in your own school",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, discount_data.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Validate date range
    if discount_data.valid_from and discount_data.valid_until:
        if discount_data.valid_from > discount_data.valid_until:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="valid_from must be before valid_until",
            )

    discount = await discount_service.create_discount(db, discount_data)
    return DiscountResponse.model_validate(discount)


@router.get("/{discount_id}", response_model=DiscountResponse)
async def get_discount(
    discount_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> DiscountResponse:
    """Get a discount by ID."""
    discount = await discount_service.get_discount_by_id(db, discount_id)
    if not discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found",
        )

    # Non-superusers can only view discounts from their school
    if not current_user.is_superuser:
        if discount.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view discounts from your own school",
            )

    return DiscountResponse.model_validate(discount)


@router.patch("/{discount_id}", response_model=DiscountResponse)
async def update_discount(
    discount_id: UUID,
    discount_data: DiscountUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> DiscountResponse:
    """Update a discount."""
    if not can_manage_discounts(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update discounts",
        )

    discount = await discount_service.get_discount_by_id(db, discount_id)
    if not discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found",
        )

    # Non-superusers can only update discounts in their own school
    if not current_user.is_superuser:
        if discount.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update discounts in your own school",
            )

    # Validate percentage if type is being changed or value is being changed
    new_type = discount_data.type or discount.type
    new_value = discount_data.value or discount.value
    if new_type == DiscountType.PERCENTAGE and new_value > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Percentage discount cannot exceed 100%",
        )

    # Validate date range
    new_from = discount_data.valid_from if discount_data.valid_from is not None else discount.valid_from
    new_until = discount_data.valid_until if discount_data.valid_until is not None else discount.valid_until
    if new_from and new_until and new_from > new_until:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="valid_from must be before valid_until",
        )

    updated_discount = await discount_service.update_discount(db, discount, discount_data)
    return DiscountResponse.model_validate(updated_discount)


@router.delete("/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discount(
    discount_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    """
    Soft delete a discount.

    Only OWNER, SUPERUSER, and DIRECTOR can delete discounts.
    """
    if current_user.role not in (Role.OWNER, Role.SUPERUSER, Role.DIRECTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete discounts",
        )

    discount = await discount_service.get_discount_by_id(db, discount_id)
    if not discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found",
        )

    # Non-superusers can only delete discounts in their own school
    if not current_user.is_superuser:
        if discount.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete discounts in your own school",
            )

    await discount_service.delete_discount(db, discount)


# ============== Student Discount Assignment Endpoints ==============


@router.get("/students/{student_id}", response_model=StudentDiscountsResponse)
async def get_student_discounts(
    student_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> StudentDiscountsResponse:
    """Get all discounts assigned to a student."""
    student = await student_service.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Non-superusers can only view students from their school
    if not current_user.is_superuser:
        if student.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view students from your own school",
            )

    student_discounts = await discount_service.get_student_discounts(db, student_id)
    
    return StudentDiscountsResponse(
        student_id=student_id,
        discounts=[DiscountResponse.model_validate(sd.discount) for sd in student_discounts],
    )


@router.post("/students", response_model=StudentDiscountResponse, status_code=status.HTTP_201_CREATED)
async def assign_discount_to_student(
    assignment: StudentDiscountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> StudentDiscountResponse:
    """Assign a discount to a student."""
    if not can_manage_discounts(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to assign discounts",
        )

    # Verify student exists
    student = await student_service.get_student_by_id(db, assignment.student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Verify discount exists
    discount = await discount_service.get_discount_by_id(db, assignment.discount_id)
    if not discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount not found",
        )

    # Non-superusers can only assign in their own school
    if not current_user.is_superuser:
        if student.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only assign discounts to students in your own school",
            )

    # Student and discount must be in the same school
    if student.school_id != discount.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student and discount must belong to the same school",
        )

    # Check if already assigned
    existing = await discount_service.get_student_discount(
        db, assignment.student_id, assignment.discount_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount is already assigned to this student",
        )

    student_discount = await discount_service.assign_discount_to_student(
        db, assignment.student_id, assignment.discount_id
    )
    return StudentDiscountResponse.model_validate(student_discount)


@router.delete(
    "/students/{student_id}/discounts/{discount_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_discount_from_student(
    student_id: UUID,
    discount_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    """Remove a discount assignment from a student."""
    if not can_manage_discounts(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to remove discounts",
        )

    # Verify assignment exists
    student_discount = await discount_service.get_student_discount(db, student_id, discount_id)
    if not student_discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discount assignment not found",
        )

    # Verify student for school check
    student = await student_service.get_student_by_id(db, student_id)
    
    # Non-superusers can only remove in their own school
    if not current_user.is_superuser:
        if student and student.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only remove discounts from students in your own school",
            )

    await discount_service.remove_discount_from_student(db, student_discount)
