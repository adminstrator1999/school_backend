"""Position service."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Position
from app.schemas.position import PositionCreate, PositionUpdate


async def get_position_by_id(
    db: AsyncSession,
    position_id: UUID,
) -> Position | None:
    """Get a position by ID."""
    result = await db.execute(
        select(Position).where(Position.id == position_id)
    )
    return result.scalar_one_or_none()


async def get_positions(
    db: AsyncSession,
    school_id: UUID | None = None,
    search: str | None = None,
    include_system: bool = True,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Position], int]:
    """Get positions with filtering.
    
    Args:
        db: Database session
        school_id: Filter by school (also includes system positions if include_system=True)
        search: Search by name
        include_system: Include system-wide positions
        skip: Offset for pagination
        limit: Max results to return
    """
    query = select(Position).where(Position.is_active == True)
    count_query = select(func.count(Position.id)).where(Position.is_active == True)

    # Filter by school - include school's positions and optionally system positions
    if school_id:
        if include_system:
            condition = or_(
                Position.school_id == school_id,
                Position.school_id.is_(None)
            )
        else:
            condition = Position.school_id == school_id
        query = query.where(condition)
        count_query = count_query.where(condition)
    else:
        # Only system positions
        query = query.where(Position.school_id.is_(None))
        count_query = count_query.where(Position.school_id.is_(None))

    if search:
        search_filter = Position.name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get positions - system positions first, then by newest created
    query = query.order_by(Position.is_system.desc(), Position.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    positions = list(result.scalars().all())

    return positions, total


async def get_positions_by_school(
    db: AsyncSession,
    school_id: UUID,
    include_system: bool = True,
) -> list[Position]:
    """Get all positions for a school (including system positions)."""
    if include_system:
        condition = or_(
            Position.school_id == school_id,
            Position.school_id.is_(None)
        )
    else:
        condition = Position.school_id == school_id
    
    query = (
        select(Position)
        .where(condition)
        .where(Position.is_active == True)
        .order_by(Position.is_system.desc(), Position.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_position(
    db: AsyncSession,
    position_data: PositionCreate,
) -> Position:
    """Create a new position."""
    position = Position(
        name=position_data.name,
        school_id=position_data.school_id,
        is_system=position_data.is_system,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return position


async def update_position(
    db: AsyncSession,
    position: Position,
    position_data: PositionUpdate,
) -> Position:
    """Update a position."""
    update_data = position_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(position, field, value)

    await db.commit()
    await db.refresh(position)
    return position


async def delete_position(
    db: AsyncSession,
    position: Position,
) -> None:
    """Soft delete a position (set is_active=False)."""
    position.is_active = False
    await db.commit()
