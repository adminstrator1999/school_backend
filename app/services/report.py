"""Report service - business logic for generating reports."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense import Expense, ExpenseCategory
from app.models.invoice import Invoice, InvoiceStatus, Payment
from app.models.student import Student
from app.models.school_class import SchoolClass


async def get_financial_summary(
    db: AsyncSession,
    school_id: UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Generate financial summary for a school within a date range."""
    
    # Get invoice totals
    invoice_query = select(
        func.count(Invoice.id).label("count"),
        func.coalesce(func.sum(Invoice.amount - Invoice.discount_amount), 0).label("total_invoiced"),
    ).where(
        Invoice.school_id == school_id,
        Invoice.period_start >= date_from,
        Invoice.period_end <= date_to,
    )
    invoice_result = await db.execute(invoice_query)
    invoice_row = invoice_result.one()
    total_invoices = invoice_row.count
    total_invoiced = invoice_row.total_invoiced or Decimal("0")

    # Get payment totals
    payment_query = select(
        func.count(Payment.id).label("count"),
        func.coalesce(func.sum(Payment.amount), 0).label("total"),
    ).where(
        Payment.school_id == school_id,
        func.date(Payment.paid_at) >= date_from,
        func.date(Payment.paid_at) <= date_to,
    )
    payment_result = await db.execute(payment_query)
    payment_row = payment_result.one()
    total_payments = payment_row.count
    total_collected = payment_row.total or Decimal("0")

    # Get payments by method
    payment_by_method_query = select(
        Payment.payment_method,
        func.sum(Payment.amount).label("total"),
    ).where(
        Payment.school_id == school_id,
        func.date(Payment.paid_at) >= date_from,
        func.date(Payment.paid_at) <= date_to,
    ).group_by(Payment.payment_method)
    
    method_result = await db.execute(payment_by_method_query)
    by_payment_method = {}
    for row in method_result:
        method = row.payment_method
        if hasattr(method, "value"):
            method = method.value
        by_payment_method[method] = row.total

    # Get expense totals
    expense_query = select(
        func.count(Expense.id).label("count"),
        func.coalesce(func.sum(Expense.amount), 0).label("total"),
    ).where(
        Expense.school_id == school_id,
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    )
    expense_result = await db.execute(expense_query)
    expense_row = expense_result.one()
    total_expense_records = expense_row.count
    total_expenses = expense_row.total or Decimal("0")

    # Get expenses by category
    expense_by_category_query = select(
        ExpenseCategory.name,
        func.sum(Expense.amount).label("total"),
    ).join(
        ExpenseCategory, Expense.category_id == ExpenseCategory.id
    ).where(
        Expense.school_id == school_id,
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    ).group_by(ExpenseCategory.name)
    
    category_result = await db.execute(expense_by_category_query)
    by_category = {row.name: row.total for row in category_result}

    # Calculate outstanding (invoiced minus collected for the period)
    total_outstanding = total_invoiced - total_collected
    if total_outstanding < 0:
        total_outstanding = Decimal("0")

    return {
        "school_id": school_id,
        "date_from": date_from,
        "date_to": date_to,
        "income": {
            "total_invoiced": total_invoiced,
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "by_payment_method": by_payment_method,
        },
        "expenses": {
            "total_expenses": total_expenses,
            "by_category": by_category,
        },
        "net_income": total_collected - total_expenses,
        "total_invoices": total_invoices,
        "total_payments": total_payments,
        "total_expense_records": total_expense_records,
    }


async def get_payment_report(
    db: AsyncSession,
    school_id: UUID,
    date_from: date,
    date_to: date,
    top_debtors_limit: int = 10,
) -> dict:
    """Generate payment report for a school."""
    
    # Count invoices by status
    status_query = select(
        Invoice.status,
        func.count(Invoice.id).label("count"),
    ).where(
        Invoice.school_id == school_id,
        Invoice.period_start >= date_from,
        Invoice.period_end <= date_to,
    ).group_by(Invoice.status)
    
    status_result = await db.execute(status_query)
    status_counts = {"pending": 0, "partial": 0, "paid": 0, "overdue": 0}
    for row in status_result:
        status = row.status
        if hasattr(status, "value"):
            status = status.value
        status_counts[status] = row.count

    # Get totals
    totals_query = select(
        func.coalesce(func.sum(Invoice.amount - Invoice.discount_amount), 0).label("invoiced"),
    ).where(
        Invoice.school_id == school_id,
        Invoice.period_start >= date_from,
        Invoice.period_end <= date_to,
    )
    totals_result = await db.execute(totals_query)
    total_invoiced = totals_result.scalar() or Decimal("0")

    # Get total collected
    collected_query = select(
        func.coalesce(func.sum(Payment.amount), 0)
    ).where(
        Payment.school_id == school_id,
        func.date(Payment.paid_at) >= date_from,
        func.date(Payment.paid_at) <= date_to,
    )
    collected_result = await db.execute(collected_query)
    total_collected = collected_result.scalar() or Decimal("0")

    total_outstanding = total_invoiced - total_collected
    if total_outstanding < 0:
        total_outstanding = Decimal("0")

    # Collection rate
    collection_rate = Decimal("0")
    if total_invoiced > 0:
        collection_rate = (total_collected / total_invoiced * 100).quantize(Decimal("0.01"))

    # Get top debtors - students with highest outstanding balances
    # Subquery for total invoiced per student
    invoiced_subq = select(
        Invoice.student_id,
        func.sum(Invoice.amount - Invoice.discount_amount).label("total_invoiced"),
    ).where(
        Invoice.school_id == school_id,
        Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE]),
    ).group_by(Invoice.student_id).subquery()

    # Subquery for total paid per student
    paid_subq = select(
        Invoice.student_id,
        func.coalesce(func.sum(Payment.amount), 0).label("total_paid"),
    ).join(
        Payment, Payment.invoice_id == Invoice.id
    ).where(
        Invoice.school_id == school_id,
    ).group_by(Invoice.student_id).subquery()

    # Main query for top debtors
    debtors_query = select(
        Student.id,
        Student.first_name,
        Student.last_name,
        SchoolClass.grade,
        SchoolClass.section,
        invoiced_subq.c.total_invoiced,
        func.coalesce(paid_subq.c.total_paid, 0).label("total_paid"),
    ).join(
        invoiced_subq, Student.id == invoiced_subq.c.student_id
    ).outerjoin(
        paid_subq, Student.id == paid_subq.c.student_id
    ).outerjoin(
        SchoolClass, Student.school_class_id == SchoolClass.id
    ).where(
        Student.school_id == school_id,
    ).order_by(
        (invoiced_subq.c.total_invoiced - func.coalesce(paid_subq.c.total_paid, 0)).desc()
    ).limit(top_debtors_limit)

    debtors_result = await db.execute(debtors_query)
    top_debtors = []
    for row in debtors_result:
        outstanding = row.total_invoiced - row.total_paid
        if outstanding > 0:
            # Build class name from grade and section
            class_name = None
            if row.grade is not None:
                suffixes = {1: "st", 2: "nd", 3: "rd"}
                suffix = suffixes.get(row.grade if row.grade < 4 else 0, "th")
                class_name = f"{row.grade}{suffix} {row.section}"
            top_debtors.append({
                "student_id": row.id,
                "student_name": f"{row.first_name} {row.last_name}",
                "class_name": class_name,
                "total_invoiced": row.total_invoiced,
                "total_paid": row.total_paid,
                "outstanding": outstanding,
                "last_payment_date": None,  # Could add this with another query if needed
            })

    return {
        "school_id": school_id,
        "date_from": date_from,
        "date_to": date_to,
        "invoice_status_counts": status_counts,
        "total_invoiced": total_invoiced,
        "total_collected": total_collected,
        "total_outstanding": total_outstanding,
        "collection_rate": collection_rate,
        "top_debtors": top_debtors,
    }


async def get_expense_report(
    db: AsyncSession,
    school_id: UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Generate expense report for a school."""
    
    # Get totals
    totals_query = select(
        func.count(Expense.id).label("count"),
        func.coalesce(func.sum(Expense.amount), 0).label("total"),
    ).where(
        Expense.school_id == school_id,
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    )
    totals_result = await db.execute(totals_query)
    totals_row = totals_result.one()
    expense_count = totals_row.count
    total_expenses = totals_row.total or Decimal("0")

    average_expense = Decimal("0")
    if expense_count > 0:
        average_expense = (total_expenses / expense_count).quantize(Decimal("0.01"))

    # Get breakdown by category
    category_query = select(
        ExpenseCategory.id,
        ExpenseCategory.name,
        func.count(Expense.id).label("count"),
        func.sum(Expense.amount).label("total"),
    ).join(
        ExpenseCategory, Expense.category_id == ExpenseCategory.id
    ).where(
        Expense.school_id == school_id,
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    ).group_by(ExpenseCategory.id, ExpenseCategory.name).order_by(
        func.sum(Expense.amount).desc()
    )

    category_result = await db.execute(category_query)
    by_category = []
    for row in category_result:
        percentage = Decimal("0")
        if total_expenses > 0:
            percentage = (row.total / total_expenses * 100).quantize(Decimal("0.01"))
        by_category.append({
            "category_id": row.id,
            "category_name": row.name,
            "total_amount": row.total,
            "expense_count": row.count,
            "percentage_of_total": percentage,
        })

    return {
        "school_id": school_id,
        "date_from": date_from,
        "date_to": date_to,
        "total_expenses": total_expenses,
        "expense_count": expense_count,
        "average_expense": average_expense,
        "by_category": by_category,
    }


async def get_monthly_trend(
    db: AsyncSession,
    school_id: UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Generate monthly income/expense trend report."""
    
    # Get monthly payments (income)
    month_expr = func.to_char(Payment.paid_at, 'YYYY-MM')
    income_query = select(
        month_expr.label("month"),
        func.sum(Payment.amount).label("total"),
    ).where(
        Payment.school_id == school_id,
        func.date(Payment.paid_at) >= date_from,
        func.date(Payment.paid_at) <= date_to,
    ).group_by(
        month_expr
    ).order_by(
        month_expr
    )

    income_result = await db.execute(income_query)
    income_by_month = {row.month: row.total for row in income_result}

    # Get monthly expenses
    expense_month_expr = func.to_char(Expense.expense_date, 'YYYY-MM')
    expense_query = select(
        expense_month_expr.label("month"),
        func.sum(Expense.amount).label("total"),
    ).where(
        Expense.school_id == school_id,
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    ).group_by(
        expense_month_expr
    ).order_by(
        expense_month_expr
    )

    expense_result = await db.execute(expense_query)
    expense_by_month = {row.month: row.total for row in expense_result}

    # Combine into monthly data
    all_months = sorted(set(income_by_month.keys()) | set(expense_by_month.keys()))
    months = []
    for month in all_months:
        income = income_by_month.get(month, Decimal("0"))
        expenses = expense_by_month.get(month, Decimal("0"))
        months.append({
            "month": month,
            "income": income,
            "expenses": expenses,
            "net": income - expenses,
        })

    return {
        "school_id": school_id,
        "months": months,
    }
