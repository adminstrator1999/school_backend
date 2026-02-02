"""Recurring Expense service."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.expense import Expense, ExpenseCategory, RecurringExpense, RecurrenceType
from app.schemas.recurring_expense import (
    RecurringExpenseCreate,
    RecurringExpenseUpdate,
)


async def get_recurring_expenses(
    db: AsyncSession,
    school_id: UUID | None = None,
    category_id: UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[RecurringExpense], int]:
    """Get paginated list of recurring expenses with filters."""
    query = select(RecurringExpense).options(joinedload(RecurringExpense.category))

    if school_id:
        query = query.where(RecurringExpense.school_id == school_id)
    if category_id:
        query = query.where(RecurringExpense.category_id == category_id)
    if is_active is not None:
        query = query.where(RecurringExpense.is_active == is_active)
    if search:
        query = query.where(RecurringExpense.name.ilike(f"%{search}%"))

    # Count query
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Main query with pagination
    query = query.order_by(RecurringExpense.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    recurring_expenses = list(result.scalars().all())

    return recurring_expenses, total


async def get_recurring_expense(
    db: AsyncSession,
    recurring_expense_id: UUID,
) -> RecurringExpense | None:
    """Get a single recurring expense by ID."""
    query = (
        select(RecurringExpense)
        .options(joinedload(RecurringExpense.category))
        .where(RecurringExpense.id == recurring_expense_id)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def create_recurring_expense(
    db: AsyncSession,
    recurring_expense_data: RecurringExpenseCreate,
) -> RecurringExpense:
    """Create a new recurring expense."""
    recurring_expense = RecurringExpense(
        school_id=recurring_expense_data.school_id,
        category_id=recurring_expense_data.category_id,
        name=recurring_expense_data.name,
        amount=recurring_expense_data.amount,
        recurrence=recurring_expense_data.recurrence,
        day_of_month=recurring_expense_data.day_of_month,
        is_active=recurring_expense_data.is_active,
    )
    db.add(recurring_expense)
    await db.commit()
    await db.refresh(recurring_expense)

    # Load category relationship
    query = (
        select(RecurringExpense)
        .options(joinedload(RecurringExpense.category))
        .where(RecurringExpense.id == recurring_expense.id)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def update_recurring_expense(
    db: AsyncSession,
    recurring_expense: RecurringExpense,
    recurring_expense_data: RecurringExpenseUpdate,
) -> RecurringExpense:
    """Update a recurring expense."""
    update_data = recurring_expense_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(recurring_expense, field, value)

    await db.commit()
    await db.refresh(recurring_expense)

    # Load category relationship
    query = (
        select(RecurringExpense)
        .options(joinedload(RecurringExpense.category))
        .where(RecurringExpense.id == recurring_expense.id)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def delete_recurring_expense(
    db: AsyncSession,
    recurring_expense: RecurringExpense,
) -> None:
    """Delete a recurring expense."""
    await db.delete(recurring_expense)
    await db.commit()


async def generate_expenses_from_recurring(
    db: AsyncSession,
    school_id: UUID,
    created_by_id: UUID,
    target_date: date | None = None,
) -> tuple[list[UUID], int]:
    """
    Generate expenses from recurring expense templates.
    
    Returns the IDs of generated expenses and count.
    """
    if target_date is None:
        target_date = date.today()

    # Get active recurring expenses for this school that are due
    query = select(RecurringExpense).where(
        RecurringExpense.school_id == school_id,
        RecurringExpense.is_active == True,
        RecurringExpense.day_of_month == target_date.day,
    )

    result = await db.execute(query)
    recurring_expenses = list(result.scalars().all())

    generated_expense_ids: list[UUID] = []

    for recurring in recurring_expenses:
        # Check if already generated for this period
        if recurring.last_generated_at:
            if _should_skip_generation(recurring, target_date):
                continue

        # Create expense
        expense = Expense(
            school_id=recurring.school_id,
            category_id=recurring.category_id,
            description=f"{recurring.name} ({recurring.recurrence})",
            amount=recurring.amount,
            expense_date=target_date,
            created_by_id=created_by_id,
            recurring_expense_id=recurring.id,
        )
        db.add(expense)
        await db.flush()

        # Update last generated date
        recurring.last_generated_at = target_date

        generated_expense_ids.append(expense.id)

    await db.commit()
    return generated_expense_ids, len(generated_expense_ids)


def _should_skip_generation(recurring: RecurringExpense, target_date: date) -> bool:
    """
    Determine if expense generation should be skipped based on recurrence.
    
    Returns True if the expense was already generated for the current period.
    """
    last_gen = recurring.last_generated_at
    if not last_gen:
        return False

    if recurring.recurrence == RecurrenceType.MONTHLY:
        # Skip if generated in the same month
        return (
            last_gen.year == target_date.year
            and last_gen.month == target_date.month
        )
    elif recurring.recurrence == RecurrenceType.QUARTERLY:
        # Skip if generated in the same quarter
        last_quarter = (last_gen.month - 1) // 3
        target_quarter = (target_date.month - 1) // 3
        return last_gen.year == target_date.year and last_quarter == target_quarter
    elif recurring.recurrence == RecurrenceType.YEARLY:
        # Skip if generated in the same year
        return last_gen.year == target_date.year

    return False


async def get_due_recurring_expenses(
    db: AsyncSession,
    school_id: UUID,
    target_date: date | None = None,
) -> list[RecurringExpense]:
    """Get recurring expenses that are due for generation on the target date."""
    if target_date is None:
        target_date = date.today()

    query = (
        select(RecurringExpense)
        .options(joinedload(RecurringExpense.category))
        .where(
            RecurringExpense.school_id == school_id,
            RecurringExpense.is_active == True,
            RecurringExpense.day_of_month == target_date.day,
        )
    )

    result = await db.execute(query)
    all_due = list(result.scalars().all())

    # Filter out already generated ones
    due_expenses = []
    for recurring in all_due:
        if not _should_skip_generation(recurring, target_date):
            due_expenses.append(recurring)

    return due_expenses
