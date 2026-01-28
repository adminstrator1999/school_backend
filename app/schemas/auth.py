"""Authentication schemas."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.validators import PhoneNumber


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    user_id: UUID | None = None


class LoginRequest(BaseModel):
    """Login request schema."""

    phone_number: PhoneNumber
    password: str = Field(..., min_length=6)
