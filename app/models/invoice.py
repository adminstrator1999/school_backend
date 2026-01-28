"""Invoice and Payment models."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel


class InvoiceStatus(str, Enum):
    """Invoice payment status."""

    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"


class PaymentMethod(str, Enum):
    """How payment was received."""

    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"


class Invoice(BaseModel):
    """Invoice for student payment."""

    __tablename__ = "invoices"

    school_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Period covered
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Amounts
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )  # Original amount before discount
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
        server_default="0",
    )  # Total discount applied
    
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        String(20),
        default=InvoiceStatus.PENDING,
        server_default="pending",
    )
    
    note: Mapped[str | None] = mapped_column(Text)

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="invoices")
    student: Mapped["Student"] = relationship("Student", back_populates="invoices")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="invoice")

    @property
    def total_amount(self) -> Decimal:
        """Amount after discount."""
        return self.amount - self.discount_amount

    @property
    def paid_amount(self) -> Decimal:
        """Sum of all payments."""
        return sum((p.amount for p in self.payments), Decimal(0))

    @property
    def remaining_amount(self) -> Decimal:
        """Amount still owed."""
        return self.total_amount - self.paid_amount

    def update_status(self) -> None:
        """Update status based on payments and due date."""
        if self.paid_amount >= self.total_amount:
            self.status = InvoiceStatus.PAID
        elif self.paid_amount > 0:
            self.status = InvoiceStatus.PARTIAL
        elif date.today() > self.due_date:
            self.status = InvoiceStatus.OVERDUE
        else:
            self.status = InvoiceStatus.PENDING

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, student={self.student_id}, status={self.status})>"


class Payment(BaseModel):
    """Actual payment received for an invoice."""

    __tablename__ = "payments"

    school_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        String(20),
        nullable=False,
    )
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    received_by_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )  # User (accountant) who received payment
    
    note: Mapped[str | None] = mapped_column(Text)

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="payments")
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")
    received_by: Mapped["User"] = relationship("User", back_populates="received_payments")

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, amount={self.amount})>"
