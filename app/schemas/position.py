"""Position schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    """Schema for creating a position."""

    name: str = Field(..., min_length=1, max_length=100)
    school_id: UUID | None = None  # None for system-wide positions
    is_system: bool = False


class PositionUpdate(BaseModel):
    """Schema for updating a position."""

    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None


class PositionResponse(BaseModel):
    """Schema for position response."""

    id: UUID
    name: str
    school_id: UUID | None
    is_system: bool
    is_active: bool

    model_config = {"from_attributes": True}


class PositionListResponse(BaseModel):
    """Schema for paginated position list."""

    items: list[PositionResponse]
    total: int
