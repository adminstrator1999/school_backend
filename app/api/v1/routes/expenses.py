"""Expense API routes."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import Role
from app.schemas.expense import (
    CategoryInfo,
    CreatedByInfo,
    EmployeeInfo,
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseSummary,
    ExpenseUpdate,
)
from app.services import expense as expense_service
from app.services import expense_category as category_service
from app.services import employee as employee_service
from app.services import school as school_service

router = APIRouter(prefix="/expenses", tags=["Expenses"])


# ============== Helper Functions ==============


def can_manage_expenses(user) -> bool:
    """Check if user has permission to create/update expenses."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.SHAREHOLDER,
        Role.ACCOUNTANT,
    )


def _build_expense_response(expense) -> ExpenseResponse:
    """Build expense response with nested objects."""
    return ExpenseResponse(
        id=expense.id,
        school_id=expense.school_id,
        category_id=expense.category_id,
        employee_id=expense.employee_id,
        recurring_expense_id=expense.recurring_expense_id,
        amount=expense.amount,
        description=expense.description,
        expense_date=expense.expense_date,
        created_by_id=expense.created_by_id,
        category=CategoryInfo(
            id=expense.category.id,
            name=expense.category.name,
            is_system=expense.category.is_system,
        ),
        employee=EmployeeInfo(
            id=expense.employee.id,
            first_name=expense.employee.first_name,
            last_name=expense.employee.last_name,
        ) if expense.employee else None,
        created_by=CreatedByInfo(
            id=expense.created_by.id,
            first_name=expense.created_by.first_name,
            last_name=expense.created_by.last_name,
        ),
    )


# ============== Endpoints ==============


@router.get("", response_model=ExpenseListResponse)
async def list_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    category_id: UUID | None = Query(None, description="Filter by category ID"),
    employee_id: UUID | None = Query(None, description="Filter by employee ID"),
    date_from: date | None = Query(None, description="Filter from date"),
    date_to: date | None = Query(None, description="Filter to date"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Max number of records"),
) -> ExpenseListResponse:
    """
    List expenses with optional filters.

    - OWNER/SUPERUSER: Can see all expenses, can filter by school_id
    - Others: Can only see expenses from their school
    """
    # Non-superusers can only see their own school's expenses
    if not current_user.is_superuser:
        school_id = current_user.school_id

    expenses, total = await expense_service.get_expenses(
        db,
        school_id=school_id,
        category_id=category_id,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )

    return ExpenseListResponse(
        items=[_build_expense_response(e) for e in expenses],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/summary", response_model=ExpenseSummary)
async def get_expense_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID = Query(..., description="School ID"),
    date_from: date | None = Query(None, description="Filter from date"),
    date_to: date | None = Query(None, description="Filter to date"),
) -> ExpenseSummary:
    """
    Get expense summary statistics for a school.
    """
    # Non-superusers can only see their own school's summary
    if not current_user.is_superuser:
        if school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view expenses from other schools",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    summary = await expense_service.get_expense_summary(db, school_id, date_from, date_to)
    return ExpenseSummary(**summary)


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    expense_data: ExpenseCreate,
) -> ExpenseResponse:
    """
    Create a new expense.

    - OWNER/SUPERUSER: Can create for any school
    - DIRECTOR/SHAREHOLDER/ACCOUNTANT: Can create for their school only
    """
    if not can_manage_expenses(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to create expenses",
        )

    # Non-superusers can only create for their own school
    if not current_user.is_superuser:
        if expense_data.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create expenses for other schools",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, expense_data.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Verify category exists and belongs to school (or is system category)
    category = await category_service.get_expense_category_by_id(
        db, expense_data.category_id, school_id=expense_data.school_id
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense category not found",
        )

    # If employee_id provided, verify it exists and belongs to school
    if expense_data.employee_id:
        employee = await employee_service.get_employee_by_id(
            db, expense_data.employee_id
        )
        if not employee or employee.school_id != expense_data.school_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found",
            )

    expense = await expense_service.create_expense(db, expense_data, current_user.id)
    return _build_expense_response(expense)


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    expense_id: UUID,
) -> ExpenseResponse:
    """
    Get an expense by ID.
    """
    # Determine school filter
    school_id = None if current_user.is_superuser else current_user.school_id

    expense = await expense_service.get_expense_by_id(db, expense_id, school_id=school_id)
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    return _build_expense_response(expense)


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    expense_id: UUID,
    expense_data: ExpenseUpdate,
) -> ExpenseResponse:
    """
    Update an expense.
    """
    if not can_manage_expenses(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update expenses",
        )

    # Determine school filter
    school_id = None if current_user.is_superuser else current_user.school_id

    expense = await expense_service.get_expense_by_id(db, expense_id, school_id=school_id)
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    # Non-superusers can only update their own school's expenses
    if not current_user.is_superuser:
        if expense.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update expenses from other schools",
            )

    # If category_id is being updated, verify it exists
    if expense_data.category_id:
        category = await category_service.get_expense_category_by_id(
            db, expense_data.category_id, school_id=expense.school_id
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense category not found",
            )

    # If employee_id is being updated, verify it exists
    if expense_data.employee_id:
        employee = await employee_service.get_employee_by_id(
            db, expense_data.employee_id
        )
        if not employee or employee.school_id != expense.school_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found",
            )

    expense = await expense_service.update_expense(db, expense, expense_data)
    return _build_expense_response(expense)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    expense_id: UUID,
) -> None:
    """
    Delete an expense.

    - Only OWNER/SUPERUSER/DIRECTOR can delete
    """
    if current_user.role not in (Role.OWNER, Role.SUPERUSER, Role.DIRECTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete expenses",
        )

    # Determine school filter
    school_id = None if current_user.is_superuser else current_user.school_id

    expense = await expense_service.get_expense_by_id(db, expense_id, school_id=school_id)
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    # Non-superusers can only delete their own school's expenses
    if not current_user.is_superuser:
        if expense.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete expenses from other schools",
            )

    await expense_service.delete_expense(db, expense)
