"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.permissions import Role
from app.models.user import Language, Theme
from app.schemas.validators import PhoneNumber


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    phone_number: PhoneNumber
    password: str = Field(..., min_length=6)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: Role = Role.STAFF
    school_id: UUID | None = None
    profile_picture: str | None = Field(None, max_length=500)
    language: Language = Language.UZ
    theme: Theme = Theme.LIGHT


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    phone_number: PhoneNumber | None = None
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    role: Role | None = None
    school_id: UUID | None = None
    profile_picture: str | None = Field(None, max_length=500)
    is_active: bool | None = None
    language: Language | None = None
    theme: Theme | None = None


class UserUpdateMe(BaseModel):
    """Schema for user updating their own profile."""

    phone_number: PhoneNumber | None = None
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    profile_picture: str | None = Field(None, max_length=500)
    language: Language | None = None
    theme: Theme | None = None


class PasswordChange(BaseModel):
    """Schema for changing password."""

    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    """User response schema."""

    id: UUID
    phone_number: str
    first_name: str
    last_name: str
    role: Role
    school_id: UUID | None
    profile_picture: str | None
    is_active: bool
    language: Language
    theme: Theme
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated list of users."""

    items: list[UserResponse]
    total: int
    skip: int
    limit: int
