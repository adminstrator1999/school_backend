"""School schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SchoolCreate(BaseModel):
    """Schema for creating a new school."""

    name: str = Field(..., min_length=1, max_length=255)
    address: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=50)
    logo: str | None = Field(None, max_length=500)


class SchoolUpdate(BaseModel):
    """Schema for updating a school."""

    name: str | None = Field(None, min_length=1, max_length=255)
    address: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=50)
    logo: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class SchoolSubscriptionUpdate(BaseModel):
    """Schema for updating school subscription."""

    subscription_starts_at: datetime | None = None
    subscription_expires_at: datetime | None = None


class SchoolResponse(BaseModel):
    """School response schema."""

    id: UUID
    name: str
    address: str | None
    phone: str | None
    logo: str | None
    subscription_starts_at: datetime | None
    subscription_expires_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SchoolListResponse(BaseModel):
    """Paginated list of schools."""

    items: list[SchoolResponse]
    total: int
    skip: int
    limit: int
