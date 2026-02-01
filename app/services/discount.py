"""Discount service layer."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discount import Discount, DiscountType, StudentDiscount
from app.schemas.discount import DiscountCreate, DiscountUpdate


# ============== Discount CRUD ==============


async def get_discount_by_id(
    db: AsyncSession,
    discount_id: UUID,
) -> Discount | None:
    """Get a discount by ID."""
    result = await db.execute(
        select(Discount).where(Discount.id == discount_id)
    )
    return result.scalar_one_or_none()


async def get_discounts(
    db: AsyncSession,
    *,
    school_id: UUID | None = None,
    discount_type: DiscountType | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Discount], int]:
    """Get discounts with optional filters."""
    query = select(Discount)
    count_query = select(func.count(Discount.id))

    if school_id:
        query = query.where(Discount.school_id == school_id)
        count_query = count_query.where(Discount.school_id == school_id)

    if discount_type:
        query = query.where(Discount.type == discount_type)
        count_query = count_query.where(Discount.type == discount_type)

    if is_active is not None:
        query = query.where(Discount.is_active == is_active)
        count_query = count_query.where(Discount.is_active == is_active)

    if search:
        search_filter = Discount.name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Order by name
    query = query.order_by(Discount.name).offset(skip).limit(limit)

    result = await db.execute(query)
    discounts = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return discounts, total


async def get_discounts_by_school(
    db: AsyncSession,
    school_id: UUID,
    *,
    is_active: bool | None = True,
) -> list[Discount]:
    """Get all discounts for a school."""
    query = select(Discount).where(Discount.school_id == school_id)

    if is_active is not None:
        query = query.where(Discount.is_active == is_active)

    result = await db.execute(query.order_by(Discount.name))
    return list(result.scalars().all())


async def create_discount(
    db: AsyncSession,
    discount_data: DiscountCreate,
) -> Discount:
    """Create a new discount."""
    discount = Discount(
        school_id=discount_data.school_id,
        name=discount_data.name,
        type=discount_data.type,
        value=discount_data.value,
        valid_from=discount_data.valid_from,
        valid_until=discount_data.valid_until,
    )
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return discount


async def update_discount(
    db: AsyncSession,
    discount: Discount,
    discount_data: DiscountUpdate,
) -> Discount:
    """Update a discount."""
    update_data = discount_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(discount, field, value)

    await db.commit()
    await db.refresh(discount)
    return discount


async def delete_discount(
    db: AsyncSession,
    discount: Discount,
) -> None:
    """Soft delete a discount (set is_active=False)."""
    discount.is_active = False
    await db.commit()


# ============== Student Discount Assignment ==============


async def get_student_discount(
    db: AsyncSession,
    student_id: UUID,
    discount_id: UUID,
) -> StudentDiscount | None:
    """Check if a student has a specific discount."""
    result = await db.execute(
        select(StudentDiscount)
        .options(selectinload(StudentDiscount.discount))
        .where(
            StudentDiscount.student_id == student_id,
            StudentDiscount.discount_id == discount_id,
        )
    )
    return result.scalar_one_or_none()


async def get_student_discounts(
    db: AsyncSession,
    student_id: UUID,
) -> list[StudentDiscount]:
    """Get all discounts assigned to a student."""
    result = await db.execute(
        select(StudentDiscount)
        .options(selectinload(StudentDiscount.discount))
        .where(StudentDiscount.student_id == student_id)
    )
    return list(result.scalars().all())


async def assign_discount_to_student(
    db: AsyncSession,
    student_id: UUID,
    discount_id: UUID,
) -> StudentDiscount:
    """Assign a discount to a student."""
    student_discount = StudentDiscount(
        student_id=student_id,
        discount_id=discount_id,
    )
    db.add(student_discount)
    await db.commit()
    await db.refresh(student_discount)
    
    # Reload with discount relationship
    result = await db.execute(
        select(StudentDiscount)
        .options(selectinload(StudentDiscount.discount))
        .where(StudentDiscount.id == student_discount.id)
    )
    return result.scalar_one()


async def remove_discount_from_student(
    db: AsyncSession,
    student_discount: StudentDiscount,
) -> None:
    """Remove a discount assignment from a student."""
    await db.delete(student_discount)
    await db.commit()
