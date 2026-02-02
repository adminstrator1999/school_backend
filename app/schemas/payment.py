"""Payment schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.invoice import PaymentMethod


class PaymentCreate(BaseModel):
    """Schema for creating a payment."""

    invoice_id: UUID
    amount: Decimal = Field(gt=0, description="Payment amount")
    payment_method: PaymentMethod
    note: str | None = None


class PaymentUpdate(BaseModel):
    """Schema for updating a payment."""

    amount: Decimal | None = Field(default=None, gt=0)
    payment_method: PaymentMethod | None = None
    note: str | None = None


class InvoiceInfo(BaseModel):
    """Nested invoice info for payment response."""

    id: UUID
    student_id: UUID
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)


class ReceivedByInfo(BaseModel):
    """Info about user who received payment."""

    id: UUID
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    """Schema for payment response."""

    id: UUID
    school_id: UUID
    invoice_id: UUID
    invoice: InvoiceInfo | None = None
    amount: Decimal
    payment_method: PaymentMethod
    paid_at: datetime
    received_by_id: UUID
    received_by: ReceivedByInfo | None = None
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentListResponse(BaseModel):
    """Schema for paginated payment list."""

    items: list[PaymentResponse]
    total: int
    skip: int
    limit: int


class PaymentSummary(BaseModel):
    """Payment summary statistics."""

    total_payments: int
    total_amount: Decimal
    by_method: dict[str, Decimal]
