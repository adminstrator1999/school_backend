"""Recurring Expense API routes."""

import math
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import Role
from app.schemas.recurring_expense import (
    GenerateExpensesRequest,
    GenerateExpensesResponse,
    RecurringExpenseCreate,
    RecurringExpenseListResponse,
    RecurringExpenseUpdate,
    RecurringExpenseWithCategory,
)
from app.services import recurring_expense as recurring_expense_service
from app.services import expense_category as category_service
from app.services import school as school_service

router = APIRouter(prefix="/recurring-expenses", tags=["Recurring Expenses"])


# Roles that can manage recurring expenses
MANAGE_ROLES = {
    Role.OWNER,
    Role.SUPERUSER,
    Role.DIRECTOR,
    Role.ACCOUNTANT,
}


def check_manage_permission(user: CurrentUser) -> None:
    """Check if user can manage recurring expenses."""
    if user.role not in MANAGE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to manage recurring expenses",
        )


@router.get("", response_model=RecurringExpenseListResponse)
async def list_recurring_expenses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = None,
    category_id: UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """
    List recurring expenses with optional filters.
    
    Available to: OWNER, SUPERUSER, DIRECTOR, ACCOUNTANT
    """
    check_manage_permission(current_user)

    # Non-global users can only see their school's data
    if current_user.role not in {Role.OWNER, Role.SUPERUSER}:
        school_id = current_user.school_id

    skip = (page - 1) * size
    recurring_expenses, total = await recurring_expense_service.get_recurring_expenses(
        db,
        school_id=school_id,
        category_id=category_id,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=size,
    )

    items = []
    for re in recurring_expenses:
        item = RecurringExpenseWithCategory(
            id=re.id,
            school_id=re.school_id,
            category_id=re.category_id,
            name=re.name,
            amount=re.amount,
            recurrence=re.recurrence,
            day_of_month=re.day_of_month,
            is_active=re.is_active,
            last_generated_at=re.last_generated_at,
            created_at=re.created_at,
            updated_at=re.updated_at,
            category_name=re.category.name if re.category else None,
        )
        items.append(item)

    return RecurringExpenseListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.post("", response_model=RecurringExpenseWithCategory, status_code=status.HTTP_201_CREATED)
async def create_recurring_expense(
    recurring_expense_data: RecurringExpenseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Create a new recurring expense template.
    
    Available to: OWNER, SUPERUSER, DIRECTOR, ACCOUNTANT
    """
    check_manage_permission(current_user)

    # Non-global users can only create in their school
    if current_user.role not in {Role.OWNER, Role.SUPERUSER}:
        if recurring_expense_data.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create recurring expense for another school",
            )

    # Validate school exists
    school = await school_service.get_school_by_id(db, recurring_expense_data.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Validate category exists and belongs to school
    category = await category_service.get_expense_category_by_id(
        db, recurring_expense_data.category_id
    )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense category not found",
        )
    if category.school_id != recurring_expense_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category does not belong to this school",
        )

    recurring_expense = await recurring_expense_service.create_recurring_expense(
        db, recurring_expense_data
    )

    return RecurringExpenseWithCategory(
        id=recurring_expense.id,
        school_id=recurring_expense.school_id,
        category_id=recurring_expense.category_id,
        name=recurring_expense.name,
        amount=recurring_expense.amount,
        recurrence=recurring_expense.recurrence,
        day_of_month=recurring_expense.day_of_month,
        is_active=recurring_expense.is_active,
        last_generated_at=recurring_expense.last_generated_at,
        created_at=recurring_expense.created_at,
        updated_at=recurring_expense.updated_at,
        category_name=recurring_expense.category.name if recurring_expense.category else None,
    )


@router.get("/{recurring_expense_id}", response_model=RecurringExpenseWithCategory)
async def get_recurring_expense(
    recurring_expense_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Get a recurring expense by ID.
    
    Available to: OWNER, SUPERUSER, DIRECTOR, ACCOUNTANT
    """
    check_manage_permission(current_user)

    recurring_expense = await recurring_expense_service.get_recurring_expense(
        db, recurring_expense_id
    )
    if not recurring_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring expense not found",
        )

    # Non-global users can only view their school's data
    if current_user.role not in {Role.OWNER, Role.SUPERUSER}:
        if recurring_expense.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access recurring expense from another school",
            )

    return RecurringExpenseWithCategory(
        id=recurring_expense.id,
        school_id=recurring_expense.school_id,
        category_id=recurring_expense.category_id,
        name=recurring_expense.name,
        amount=recurring_expense.amount,
        recurrence=recurring_expense.recurrence,
        day_of_month=recurring_expense.day_of_month,
        is_active=recurring_expense.is_active,
        last_generated_at=recurring_expense.last_generated_at,
        created_at=recurring_expense.created_at,
        updated_at=recurring_expense.updated_at,
        category_name=recurring_expense.category.name if recurring_expense.category else None,
    )


@router.patch("/{recurring_expense_id}", response_model=RecurringExpenseWithCategory)
async def update_recurring_expense(
    recurring_expense_id: UUID,
    recurring_expense_data: RecurringExpenseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Update a recurring expense.
    
    Available to: OWNER, SUPERUSER, DIRECTOR, ACCOUNTANT
    """
    check_manage_permission(current_user)

    recurring_expense = await recurring_expense_service.get_recurring_expense(
        db, recurring_expense_id
    )
    if not recurring_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring expense not found",
        )

    # Non-global users can only update their school's data
    if current_user.role not in {Role.OWNER, Role.SUPERUSER}:
        if recurring_expense.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update recurring expense from another school",
            )

    # Validate category if being changed
    if recurring_expense_data.category_id:
        category = await category_service.get_expense_category_by_id(
            db, recurring_expense_data.category_id
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense category not found",
            )
        if category.school_id != recurring_expense.school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category does not belong to this school",
            )

    updated = await recurring_expense_service.update_recurring_expense(
        db, recurring_expense, recurring_expense_data
    )

    return RecurringExpenseWithCategory(
        id=updated.id,
        school_id=updated.school_id,
        category_id=updated.category_id,
        name=updated.name,
        amount=updated.amount,
        recurrence=updated.recurrence,
        day_of_month=updated.day_of_month,
        is_active=updated.is_active,
        last_generated_at=updated.last_generated_at,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        category_name=updated.category.name if updated.category else None,
    )


@router.delete("/{recurring_expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_expense(
    recurring_expense_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Delete a recurring expense.
    
    Available to: OWNER, SUPERUSER, DIRECTOR, ACCOUNTANT
    """
    check_manage_permission(current_user)

    recurring_expense = await recurring_expense_service.get_recurring_expense(
        db, recurring_expense_id
    )
    if not recurring_expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring expense not found",
        )

    # Non-global users can only delete their school's data
    if current_user.role not in {Role.OWNER, Role.SUPERUSER}:
        if recurring_expense.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete recurring expense from another school",
            )

    await recurring_expense_service.delete_recurring_expense(db, recurring_expense)


@router.post("/generate", response_model=GenerateExpensesResponse)
async def generate_expenses(
    request: GenerateExpensesRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Generate expenses from recurring expense templates.
    
    This creates actual expense records from active recurring expense templates
    that are due on the target date (or today if not specified).
    
    Available to: OWNER, SUPERUSER, DIRECTOR, ACCOUNTANT
    """
    check_manage_permission(current_user)

    # Non-global users can only generate for their school
    if current_user.role not in {Role.OWNER, Role.SUPERUSER}:
        if request.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot generate expenses for another school",
            )

    # Validate school exists
    school = await school_service.get_school_by_id(db, request.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    target_date = request.target_date or date.today()
    expense_ids, count = await recurring_expense_service.generate_expenses_from_recurring(
        db, request.school_id, current_user.id, target_date
    )

    if count == 0:
        message = f"No recurring expenses due for generation on {target_date}"
    else:
        message = f"Successfully generated {count} expense(s) from recurring templates"

    return GenerateExpensesResponse(
        generated_count=count,
        expenses=expense_ids,
        message=message,
    )


@router.get("/due/{school_id}", response_model=list[RecurringExpenseWithCategory])
async def get_due_recurring_expenses(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    target_date: date | None = None,
):
    """
    Get recurring expenses that are due for generation.
    
    This shows which recurring expense templates will generate expenses
    on the target date (or today if not specified).
    
    Available to: OWNER, SUPERUSER, DIRECTOR, ACCOUNTANT
    """
    check_manage_permission(current_user)

    # Non-global users can only view their school's data
    if current_user.role not in {Role.OWNER, Role.SUPERUSER}:
        if school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view due expenses for another school",
            )

    due_expenses = await recurring_expense_service.get_due_recurring_expenses(
        db, school_id, target_date
    )

    return [
        RecurringExpenseWithCategory(
            id=re.id,
            school_id=re.school_id,
            category_id=re.category_id,
            name=re.name,
            amount=re.amount,
            recurrence=re.recurrence,
            day_of_month=re.day_of_month,
            is_active=re.is_active,
            last_generated_at=re.last_generated_at,
            created_at=re.created_at,
            updated_at=re.updated_at,
            category_name=re.category.name if re.category else None,
        )
        for re in due_expenses
    ]
