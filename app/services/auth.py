"""Authentication service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import User


async def get_user_by_phone(db: AsyncSession, phone_number: str) -> User | None:
    """Get user by phone number."""
    result = await db.execute(
        select(User).where(User.phone_number == phone_number)
    )
    return result.scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession, 
    phone_number: str, 
    password: str
) -> User | None:
    """Authenticate user with phone and password."""
    user = await get_user_by_phone(db, phone_number)
    
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user
