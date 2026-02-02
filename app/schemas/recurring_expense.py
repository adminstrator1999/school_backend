"""Recurring Expense schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.expense import RecurrenceType


class RecurringExpenseBase(BaseModel):
    """Base schema for recurring expenses."""

    name: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    category_id: UUID
    recurrence: RecurrenceType
    day_of_month: int = Field(default=1, ge=1, le=31)


class RecurringExpenseCreate(RecurringExpenseBase):
    """Schema for creating a recurring expense."""

    school_id: UUID
    is_active: bool = True

    @field_validator("day_of_month")
    @classmethod
    def validate_day_of_month(cls, v: int) -> int:
        """Validate day of month is reasonable."""
        if v < 1 or v > 31:
            raise ValueError("Day of month must be between 1 and 31")
        return v


class RecurringExpenseUpdate(BaseModel):
    """Schema for updating a recurring expense."""

    name: str | None = Field(None, min_length=1, max_length=255)
    amount: Decimal | None = Field(None, gt=0, decimal_places=2)
    category_id: UUID | None = None
    recurrence: RecurrenceType | None = None
    day_of_month: int | None = Field(None, ge=1, le=31)
    is_active: bool | None = None


class RecurringExpenseResponse(BaseModel):
    """Schema for recurring expense response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_id: UUID
    category_id: UUID
    name: str
    amount: Decimal
    recurrence: RecurrenceType
    day_of_month: int
    is_active: bool
    last_generated_at: date | None
    created_at: datetime
    updated_at: datetime


class RecurringExpenseWithCategory(RecurringExpenseResponse):
    """Recurring expense response with category details."""

    category_name: str | None = None


class RecurringExpenseListResponse(BaseModel):
    """Schema for paginated recurring expense list."""

    items: list[RecurringExpenseWithCategory]
    total: int
    page: int
    size: int
    pages: int


class GenerateExpensesRequest(BaseModel):
    """Request schema for generating expenses from recurring templates."""

    school_id: UUID
    target_date: date | None = None  # If None, use today


class GenerateExpensesResponse(BaseModel):
    """Response schema for expense generation."""

    generated_count: int
    expenses: list[UUID]  # IDs of generated expenses
    message: str
