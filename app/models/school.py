"""School model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel


class School(BaseModel):
    """School model - represents a tenant in the system."""

    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(50))
    
    # Subscription tracking
    subscription_starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="school")
    students: Mapped[list["Student"]] = relationship("Student", back_populates="school")
    discounts: Mapped[list["Discount"]] = relationship("Discount", back_populates="school")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="school")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="school")
    employees: Mapped[list["Employee"]] = relationship("Employee", back_populates="school")
    expense_categories: Mapped[list["ExpenseCategory"]] = relationship(
        "ExpenseCategory", back_populates="school"
    )
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="school")
    recurring_expenses: Mapped[list["RecurringExpense"]] = relationship(
        "RecurringExpense", back_populates="school"
    )

    @property
    def is_subscription_active(self) -> bool:
        """Check if school has active subscription."""
        if not self.subscription_expires_at:
            return False
        return datetime.now(self.subscription_expires_at.tzinfo) < self.subscription_expires_at

    def __repr__(self) -> str:
        return f"<School(id={self.id}, name={self.name})>"
