"""Schemas for school classes."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SchoolClassCreate(BaseModel):
    """Schema for creating a new school class."""

    school_id: UUID
    homeroom_teacher_id: UUID | None = None
    grade: int = Field(..., ge=1, le=11)
    section: str = Field(..., min_length=1, max_length=10)


class SchoolClassUpdate(BaseModel):
    """Schema for updating a school class."""

    homeroom_teacher_id: UUID | None = None
    grade: int | None = Field(None, ge=1, le=11)
    section: str | None = Field(None, min_length=1, max_length=10)
    is_active: bool | None = None


class SchoolClassResponse(BaseModel):
    """School class response schema."""

    id: UUID
    school_id: UUID
    homeroom_teacher_id: UUID | None
    grade: int
    section: str
    name: str  # Computed property like "1st A"
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SchoolClassListResponse(BaseModel):
    """Paginated list of school classes."""

    items: list[SchoolClassResponse]
    total: int
    skip: int
    limit: int
