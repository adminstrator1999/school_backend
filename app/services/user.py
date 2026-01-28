"""User service."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Get user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_phone(db: AsyncSession, phone_number: str) -> User | None:
    """Get user by phone number."""
    result = await db.execute(
        select(User).where(User.phone_number == phone_number)
    )
    return result.scalar_one_or_none()


async def get_users(
    db: AsyncSession,
    *,
    school_id: UUID | None = None,
    role: Role | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[User], int]:
    """Get list of users with optional filters."""
    query = select(User)
    count_query = select(func.count()).select_from(User)
    
    # Apply filters
    if school_id is not None:
        query = query.where(User.school_id == school_id)
        count_query = count_query.where(User.school_id == school_id)
    
    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get paginated results
    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    users = list(result.scalars().all())
    
    return users, total


async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """Create a new user."""
    user = User(
        phone_number=user_data.phone_number,
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role,
        school_id=user_data.school_id,
        profile_picture=user_data.profile_picture,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


async def update_user(
    db: AsyncSession, 
    user: User, 
    user_data: UserUpdate,
) -> User:
    """Update a user."""
    update_data = user_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    new_password: str,
) -> User:
    """Change user's password."""
    user.password_hash = get_password_hash(new_password)
    await db.commit()
    await db.refresh(user)
    return user


async def deactivate_user(db: AsyncSession, user: User) -> User:
    """Soft delete a user by setting is_active to False."""
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user
