"""Invoice schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.invoice import InvoiceStatus


class InvoiceCreate(BaseModel):
    """Schema for creating an invoice."""

    school_id: UUID
    student_id: UUID
    period_start: date
    period_end: date
    amount: Decimal = Field(gt=0, description="Amount before discount")
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    due_date: date
    note: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "InvoiceCreate":
        """Validate date ranges."""
        if self.period_end < self.period_start:
            raise ValueError("period_end must be after period_start")
        if self.due_date < self.period_start:
            raise ValueError("due_date must be on or after period_start")
        return self

    @model_validator(mode="after")
    def validate_discount(self) -> "InvoiceCreate":
        """Discount cannot exceed amount."""
        if self.discount_amount > self.amount:
            raise ValueError("discount_amount cannot exceed amount")
        return self


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice."""

    period_start: date | None = None
    period_end: date | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    discount_amount: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None
    status: InvoiceStatus | None = None
    note: str | None = None


class InvoiceGenerateRequest(BaseModel):
    """Schema for generating invoices for a period."""

    school_id: UUID
    period_start: date
    period_end: date
    due_date: date
    student_ids: list[UUID] | None = None  # If None, generate for all active students

    @model_validator(mode="after")
    def validate_dates(self) -> "InvoiceGenerateRequest":
        """Validate date ranges."""
        if self.period_end < self.period_start:
            raise ValueError("period_end must be after period_start")
        if self.due_date < self.period_start:
            raise ValueError("due_date must be on or after period_start")
        return self


class StudentInfo(BaseModel):
    """Nested student info for invoice response."""

    id: UUID
    first_name: str
    last_name: str
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaymentSummary(BaseModel):
    """Summary of a payment for invoice listing."""

    id: UUID
    amount: Decimal
    payment_method: str
    paid_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""

    id: UUID
    school_id: UUID
    student_id: UUID
    student: StudentInfo | None = None
    period_start: date
    period_end: date
    amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    due_date: date
    status: InvoiceStatus
    note: str | None
    payments: list[PaymentSummary] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceListResponse(BaseModel):
    """Schema for paginated invoice list."""

    items: list[InvoiceResponse]
    total: int
    skip: int
    limit: int


class InvoiceGenerateResponse(BaseModel):
    """Response for invoice generation."""

    generated_count: int
    skipped_count: int  # Students with existing invoices for the period
    invoices: list[InvoiceResponse]
