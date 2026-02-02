"""Report schemas."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class DateRangeParams(BaseModel):
    """Common date range parameters for reports."""

    school_id: UUID
    date_from: date
    date_to: date


# ============== Financial Summary ==============


class IncomeBreakdown(BaseModel):
    """Breakdown of income sources."""

    total_invoiced: Decimal = Field(description="Total amount invoiced")
    total_collected: Decimal = Field(description="Total payments received")
    total_outstanding: Decimal = Field(description="Remaining unpaid amount")
    by_payment_method: dict[str, Decimal] = Field(description="Payments by method")


class ExpenseBreakdown(BaseModel):
    """Breakdown of expenses."""

    total_expenses: Decimal
    by_category: dict[str, Decimal]


class FinancialSummary(BaseModel):
    """Overall financial summary for a period."""

    school_id: UUID
    date_from: date
    date_to: date
    
    # Income
    income: IncomeBreakdown
    
    # Expenses
    expenses: ExpenseBreakdown
    
    # Net
    net_income: Decimal = Field(description="Income collected minus expenses")
    
    # Counts
    total_invoices: int
    total_payments: int
    total_expense_records: int


# ============== Invoice/Payment Reports ==============


class InvoiceStatusCount(BaseModel):
    """Count of invoices by status."""

    pending: int = 0
    partial: int = 0
    paid: int = 0
    overdue: int = 0


class StudentPaymentSummary(BaseModel):
    """Payment summary for a single student."""

    student_id: UUID
    student_name: str
    class_name: str | None
    total_invoiced: Decimal
    total_paid: Decimal
    outstanding: Decimal
    last_payment_date: date | None


class PaymentReport(BaseModel):
    """Detailed payment report."""

    school_id: UUID
    date_from: date
    date_to: date
    
    # Summary counts
    invoice_status_counts: InvoiceStatusCount
    
    # Totals
    total_invoiced: Decimal
    total_collected: Decimal
    total_outstanding: Decimal
    collection_rate: Decimal = Field(description="Percentage of invoiced amount collected")
    
    # Top debtors
    top_debtors: list[StudentPaymentSummary]


# ============== Expense Reports ==============


class CategoryExpenseSummary(BaseModel):
    """Expense summary for a category."""

    category_id: UUID
    category_name: str
    total_amount: Decimal
    expense_count: int
    percentage_of_total: Decimal


class ExpenseReport(BaseModel):
    """Detailed expense report."""

    school_id: UUID
    date_from: date
    date_to: date
    
    total_expenses: Decimal
    expense_count: int
    average_expense: Decimal
    
    by_category: list[CategoryExpenseSummary]


# ============== Monthly Trend Reports ==============


class MonthlyData(BaseModel):
    """Data for a single month."""

    month: str = Field(description="YYYY-MM format")
    income: Decimal
    expenses: Decimal
    net: Decimal


class MonthlyTrendReport(BaseModel):
    """Monthly income/expense trend."""

    school_id: UUID
    months: list[MonthlyData]
