"""Employee API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.core.permissions import Role
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.services import employee as employee_service
from app.services import position as position_service
from app.services import school as school_service

router = APIRouter(prefix="/employees", tags=["Employees"])


# ============== Helper Functions ==============


def can_write_employees(user) -> bool:
    """Check if user has permission to create/update employees."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.SHAREHOLDER,
        Role.ACCOUNTANT,
    )


# ============== Endpoints ==============


@router.get("", response_model=EmployeeListResponse)
async def list_employees(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    position_id: UUID | None = Query(None, description="Filter by position ID"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Search by name or phone"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Max number of records"),
) -> EmployeeListResponse:
    """
    List employees with optional filters.

    - OWNER/SUPERUSER: Can see all employees, can filter by school_id
    - Others: Can only see employees from their own school
    """
    # Non-superusers can only see their own school's employees
    if not current_user.is_superuser:
        school_id = current_user.school_id

    employees, total = await employee_service.get_employees(
        db,
        school_id=school_id,
        position_id=position_id,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
    )

    return EmployeeListResponse(
        items=[EmployeeResponse.model_validate(e) for e in employees],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    employee_data: EmployeeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> EmployeeResponse:
    """
    Create a new employee.

    - OWNER/SUPERUSER: Can create in any school
    - DIRECTOR/SHAREHOLDER/ACCOUNTANT: Can create in their own school
    """
    if not can_write_employees(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create employees",
        )

    # Non-superusers can only create employees in their own school
    if not current_user.is_superuser:
        if employee_data.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create employees in your own school",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, employee_data.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Verify position exists and is accessible
    position = await position_service.get_position_by_id(db, employee_data.position_id)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )
    # Position must be a system position or belong to the same school
    if position.school_id and position.school_id != employee_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Position does not belong to this school",
        )

    employee = await employee_service.create_employee(db, employee_data)
    return EmployeeResponse.model_validate(employee)


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> EmployeeResponse:
    """Get an employee by ID."""
    employee = await employee_service.get_employee_by_id(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    # Non-superusers can only view employees from their school
    if not current_user.is_superuser:
        if employee.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view employees from your own school",
            )

    return EmployeeResponse.model_validate(employee)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: UUID,
    employee_data: EmployeeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> EmployeeResponse:
    """Update an employee."""
    if not can_write_employees(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update employees",
        )

    employee = await employee_service.get_employee_by_id(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    # Non-superusers can only update employees in their own school
    if not current_user.is_superuser:
        if employee.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update employees in your own school",
            )

    # Validate new position if provided
    if employee_data.position_id:
        position = await position_service.get_position_by_id(db, employee_data.position_id)
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Position not found",
            )
        # Position must be a system position or belong to the same school
        if position.school_id and position.school_id != employee.school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Position does not belong to this school",
            )

    updated_employee = await employee_service.update_employee(db, employee, employee_data)
    return EmployeeResponse.model_validate(updated_employee)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Soft delete an employee.

    Only OWNER, SUPERUSER, and DIRECTOR can delete employees.
    """
    if current_user.role not in (Role.OWNER, Role.SUPERUSER, Role.DIRECTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete employees",
        )

    employee = await employee_service.get_employee_by_id(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    # Non-superusers can only delete employees in their own school
    if not current_user.is_superuser:
        if employee.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete employees in your own school",
            )

    await employee_service.deactivate_employee(db, employee)
