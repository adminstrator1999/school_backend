"""Expense schemas."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCreate(BaseModel):
    """Schema for creating an expense."""

    school_id: UUID
    category_id: UUID
    employee_id: UUID | None = None  # For salary expenses
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    description: str | None = Field(None, max_length=1000)
    expense_date: date


class ExpenseUpdate(BaseModel):
    """Schema for updating an expense."""

    category_id: UUID | None = None
    employee_id: UUID | None = None
    amount: Decimal | None = Field(None, gt=0, decimal_places=2)
    description: str | None = Field(None, max_length=1000)
    expense_date: date | None = None


class CategoryInfo(BaseModel):
    """Nested category info in expense response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_system: bool


class EmployeeInfo(BaseModel):
    """Nested employee info in expense response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str


class CreatedByInfo(BaseModel):
    """Nested user info for who created the expense."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str


class ExpenseResponse(BaseModel):
    """Schema for expense response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_id: UUID
    category_id: UUID
    employee_id: UUID | None
    recurring_expense_id: UUID | None
    amount: Decimal
    description: str | None
    expense_date: date
    created_by_id: UUID
    category: CategoryInfo
    employee: EmployeeInfo | None
    created_by: CreatedByInfo


class ExpenseListResponse(BaseModel):
    """Schema for paginated expense list."""

    items: list[ExpenseResponse]
    total: int
    skip: int
    limit: int


class ExpenseSummary(BaseModel):
    """Schema for expense summary statistics."""

    total_expenses: int
    total_amount: Decimal
    by_category: dict[str, Decimal]
