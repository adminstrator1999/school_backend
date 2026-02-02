"""Expense category schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCategoryCreate(BaseModel):
    """Schema for creating an expense category."""

    school_id: UUID
    name: str = Field(..., min_length=1, max_length=100)


class ExpenseCategoryUpdate(BaseModel):
    """Schema for updating an expense category."""

    name: str | None = Field(None, min_length=1, max_length=100)


class ExpenseCategoryResponse(BaseModel):
    """Schema for expense category response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_id: UUID | None
    name: str
    is_system: bool


class ExpenseCategoryListResponse(BaseModel):
    """Schema for paginated expense category list."""

    items: list[ExpenseCategoryResponse]
    total: int
    skip: int
    limit: int
