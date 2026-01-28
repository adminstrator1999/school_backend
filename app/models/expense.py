"""Expense models."""

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel


class ExpenseCategory(BaseModel):
    """Categories for expenses."""

    __tablename__ = "expense_categories"

    school_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=True,  # NULL for system-wide categories
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )  # System categories can't be deleted

    # Relationships
    school: Mapped["School | None"] = relationship(
        "School", back_populates="expense_categories"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<ExpenseCategory(id={self.id}, name={self.name})>"


class Employee(BaseModel):
    """Employees (teachers, staff) - separate from users."""

    __tablename__ = "employees"

    school_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    position: Mapped[str] = mapped_column(String(100), nullable=False)
    salary: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )  # Monthly salary
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="employees")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="employee")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Employee(id={self.id}, name={self.full_name})>"


class RecurrenceType(str, Enum):
    """How often expense recurs."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class RecurringExpense(BaseModel):
    """Template for auto-generated expenses (rent, etc.)."""

    __tablename__ = "recurring_expenses"

    school_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("expense_categories.id"),
        nullable=False,
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    recurrence: Mapped[RecurrenceType] = mapped_column(
        String(20),
        nullable=False,
    )
    day_of_month: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
    )  # Day to generate expense
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    last_generated_at: Mapped[date | None] = mapped_column(Date)

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="recurring_expenses")
    category: Mapped["ExpenseCategory"] = relationship("ExpenseCategory")

    def __repr__(self) -> str:
        return f"<RecurringExpense(id={self.id}, name={self.name})>"


class Expense(BaseModel):
    """Actual expense record."""

    __tablename__ = "expenses"

    school_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("expense_categories.id"),
        nullable=False,
    )
    employee_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,  # Only for salary expenses
    )
    recurring_expense_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("recurring_expenses.id", ondelete="SET NULL"),
        nullable=True,  # If generated from recurring
    )
    
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    created_by_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )  # User who recorded expense

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="expenses")
    category: Mapped["ExpenseCategory"] = relationship(
        "ExpenseCategory", back_populates="expenses"
    )
    employee: Mapped["Employee | None"] = relationship(
        "Employee", back_populates="expenses"
    )
    created_by: Mapped["User"] = relationship("User", back_populates="created_expenses")

    def __repr__(self) -> str:
        return f"<Expense(id={self.id}, amount={self.amount})>"
