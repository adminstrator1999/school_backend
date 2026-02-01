"""School service."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.schemas.school import SchoolCreate, SchoolSubscriptionUpdate, SchoolUpdate


async def get_school_by_id(db: AsyncSession, school_id: UUID) -> School | None:
    """Get school by ID."""
    result = await db.execute(select(School).where(School.id == school_id))
    return result.scalar_one_or_none()


async def get_schools(
    db: AsyncSession,
    *,
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[School], int]:
    """Get list of schools with optional filters."""
    query = select(School)
    count_query = select(func.count()).select_from(School)

    # Apply filters
    if is_active is not None:
        query = query.where(School.is_active == is_active)
        count_query = count_query.where(School.is_active == is_active)

    if search:
        search_filter = School.name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(School.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    schools = list(result.scalars().all())

    return schools, total


async def create_school(db: AsyncSession, school_data: SchoolCreate) -> School:
    """Create a new school."""
    school = School(
        name=school_data.name,
        address=school_data.address,
        phone=school_data.phone,
        logo=school_data.logo,
    )

    db.add(school)
    await db.commit()
    await db.refresh(school)

    return school


async def update_school(
    db: AsyncSession,
    school: School,
    school_data: SchoolUpdate,
) -> School:
    """Update a school."""
    update_data = school_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(school, field, value)

    await db.commit()
    await db.refresh(school)

    return school


async def update_subscription(
    db: AsyncSession,
    school: School,
    subscription_data: SchoolSubscriptionUpdate,
) -> School:
    """Update school subscription dates."""
    update_data = subscription_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(school, field, value)

    await db.commit()
    await db.refresh(school)

    return school


async def deactivate_school(db: AsyncSession, school: School) -> School:
    """Soft delete a school by setting is_active to False."""
    school.is_active = False
    await db.commit()
    await db.refresh(school)
    return school
