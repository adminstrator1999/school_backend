"""Expense category service - business logic for expense category operations."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import ExpenseCategory
from app.schemas.expense_category import ExpenseCategoryCreate, ExpenseCategoryUpdate


async def get_expense_category_by_id(
    db: AsyncSession,
    category_id: UUID,
    school_id: UUID | None = None,
) -> ExpenseCategory | None:
    """Get expense category by ID, optionally filtered by school."""
    query = select(ExpenseCategory).where(ExpenseCategory.id == category_id)
    if school_id:
        # Include system categories (school_id is NULL) or school's own categories
        query = query.where(
            or_(
                ExpenseCategory.school_id == school_id,
                ExpenseCategory.school_id.is_(None),
            )
        )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_expense_categories(
    db: AsyncSession,
    school_id: UUID | None = None,
    search: str | None = None,
    include_system: bool = True,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ExpenseCategory], int]:
    """Get expense categories with filters."""
    query = select(ExpenseCategory)

    # Apply filters
    if school_id:
        if include_system:
            # Include school's categories and system categories
            query = query.where(
                or_(
                    ExpenseCategory.school_id == school_id,
                    ExpenseCategory.school_id.is_(None),
                )
            )
        else:
            query = query.where(ExpenseCategory.school_id == school_id)
    
    if search:
        query = query.where(ExpenseCategory.name.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(ExpenseCategory.is_system.desc(), ExpenseCategory.name)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    categories = list(result.scalars().all())

    return categories, total


async def create_expense_category(
    db: AsyncSession,
    category_data: ExpenseCategoryCreate,
) -> ExpenseCategory:
    """Create a new expense category."""
    category = ExpenseCategory(
        school_id=category_data.school_id,
        name=category_data.name.strip(),
        is_system=False,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_expense_category(
    db: AsyncSession,
    category: ExpenseCategory,
    category_data: ExpenseCategoryUpdate,
) -> ExpenseCategory:
    """Update an existing expense category."""
    update_data = category_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "name" and value:
            value = value.strip()
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)
    return category


async def delete_expense_category(db: AsyncSession, category: ExpenseCategory) -> None:
    """Delete an expense category."""
    await db.delete(category)
    await db.commit()


async def check_duplicate_category(
    db: AsyncSession,
    school_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> bool:
    """Check if a category with the same name already exists for the school."""
    query = select(ExpenseCategory).where(
        ExpenseCategory.school_id == school_id,
        func.lower(ExpenseCategory.name) == name.lower().strip(),
    )
    if exclude_id:
        query = query.where(ExpenseCategory.id != exclude_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None
