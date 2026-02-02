"""Expense service - business logic for expense operations."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense import Expense, ExpenseCategory
from app.schemas.expense import ExpenseCreate, ExpenseUpdate


async def get_expense_by_id(
    db: AsyncSession,
    expense_id: UUID,
    school_id: UUID | None = None,
) -> Expense | None:
    """Get expense by ID, optionally filtered by school."""
    query = select(Expense).where(Expense.id == expense_id)
    if school_id:
        query = query.where(Expense.school_id == school_id)
    query = query.options(
        selectinload(Expense.category),
        selectinload(Expense.employee),
        selectinload(Expense.created_by),
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_expenses(
    db: AsyncSession,
    school_id: UUID | None = None,
    category_id: UUID | None = None,
    employee_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Expense], int]:
    """Get expenses with filters."""
    query = select(Expense)

    # Apply filters
    if school_id:
        query = query.where(Expense.school_id == school_id)
    if category_id:
        query = query.where(Expense.category_id == category_id)
    if employee_id:
        query = query.where(Expense.employee_id == employee_id)
    if date_from:
        query = query.where(Expense.expense_date >= date_from)
    if date_to:
        query = query.where(Expense.expense_date <= date_to)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.options(
        selectinload(Expense.category),
        selectinload(Expense.employee),
        selectinload(Expense.created_by),
    ).order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    expenses = list(result.scalars().all())

    return expenses, total


async def create_expense(
    db: AsyncSession,
    expense_data: ExpenseCreate,
    created_by_id: UUID,
) -> Expense:
    """Create a new expense."""
    expense = Expense(
        school_id=expense_data.school_id,
        category_id=expense_data.category_id,
        employee_id=expense_data.employee_id,
        amount=expense_data.amount,
        description=expense_data.description,
        expense_date=expense_data.expense_date,
        created_by_id=created_by_id,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)

    # Load relationships
    return await get_expense_by_id(db, expense.id)


async def update_expense(
    db: AsyncSession,
    expense: Expense,
    expense_data: ExpenseUpdate,
) -> Expense:
    """Update an existing expense."""
    update_data = expense_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(expense, field, value)

    await db.commit()
    await db.refresh(expense)

    return await get_expense_by_id(db, expense.id)


async def delete_expense(db: AsyncSession, expense: Expense) -> None:
    """Delete an expense."""
    await db.delete(expense)
    await db.commit()


async def get_expense_summary(
    db: AsyncSession,
    school_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Get expense summary statistics for a school."""
    query = select(Expense).where(Expense.school_id == school_id)

    if date_from:
        query = query.where(Expense.expense_date >= date_from)
    if date_to:
        query = query.where(Expense.expense_date <= date_to)

    query = query.options(selectinload(Expense.category))

    result = await db.execute(query)
    expenses = result.scalars().all()

    total_amount = Decimal("0")
    by_category: dict[str, Decimal] = {}

    for expense in expenses:
        total_amount += expense.amount
        category_name = expense.category.name
        by_category[category_name] = by_category.get(category_name, Decimal("0")) + expense.amount

    return {
        "total_expenses": len(expenses),
        "total_amount": total_amount,
        "by_category": by_category,
    }
