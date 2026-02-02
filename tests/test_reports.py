"""Tests for Reports API."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Employee, Expense, ExpenseCategory, Position
from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.models.school import School
from app.models.school_class import SchoolClass
from app.models.student import Student
from tests.conftest import auth_header


# ============== Fixtures ==============


@pytest.fixture
async def school(db: AsyncSession) -> School:
    """Create a test school."""
    school = School(name="Test School")
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


@pytest.fixture
async def school_class(db: AsyncSession, school: School) -> SchoolClass:
    """Create a test class."""
    school_class = SchoolClass(
        school_id=school.id,
        grade=5,
        section="A",
    )
    db.add(school_class)
    await db.commit()
    await db.refresh(school_class)
    return school_class


@pytest.fixture
async def student(db: AsyncSession, school: School, school_class: SchoolClass) -> Student:
    """Create a test student."""
    student = Student(
        school_id=school.id,
        school_class_id=school_class.id,
        first_name="Ali",
        last_name="Valiyev",
        parent_first_name="Vali",
        parent_last_name="Valiyev",
        parent_phone_1="+998901234567",
        monthly_fee=Decimal("1000000.00"),
        enrolled_at=date.today(),
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@pytest.fixture
async def expense_category(db: AsyncSession, school: School) -> ExpenseCategory:
    """Create a test expense category."""
    category = ExpenseCategory(
        name="Office Supplies",
        school_id=school.id,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@pytest.fixture
async def invoice(db: AsyncSession, school: School, student: Student) -> Invoice:
    """Create a test invoice."""
    today = date.today()
    invoice = Invoice(
        school_id=school.id,
        student_id=student.id,
        period_start=today.replace(day=1),
        period_end=(today.replace(day=1) + timedelta(days=30)),
        amount=Decimal("1000000.00"),
        discount_amount=Decimal("0"),
        due_date=today + timedelta(days=15),
        status=InvoiceStatus.PENDING,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@pytest.fixture
async def payment(
    db: AsyncSession,
    school: School,
    invoice: Invoice,
    owner_user,
) -> Payment:
    """Create a test payment."""
    payment = Payment(
        school_id=school.id,
        invoice_id=invoice.id,
        amount=Decimal("500000.00"),
        payment_method=PaymentMethod.CASH,
        received_by_id=owner_user.id,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@pytest.fixture
async def expense(
    db: AsyncSession,
    school: School,
    expense_category: ExpenseCategory,
    owner_user,
) -> Expense:
    """Create a test expense."""
    expense = Expense(
        school_id=school.id,
        category_id=expense_category.id,
        amount=Decimal("200000.00"),
        description="Office supplies",
        expense_date=date.today(),
        created_by_id=owner_user.id,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


# ============== Tests ==============


class TestFinancialSummary:
    """Tests for financial summary report."""

    async def test_financial_summary_empty(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test financial summary with no data."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/financial-summary",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["income"]["total_invoiced"] == "0"
        assert data["income"]["total_collected"] == "0"
        assert data["expenses"]["total_expenses"] == "0"
        assert data["net_income"] == "0"

    async def test_financial_summary_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        invoice: Invoice,
        payment: Payment,
        expense: Expense,
    ):
        """Test financial summary with data."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/financial-summary",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today + timedelta(days=30)),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["income"]["total_invoiced"] == "1000000.00"
        assert data["income"]["total_collected"] == "500000.00"
        assert data["expenses"]["total_expenses"] == "200000.00"
        assert data["net_income"] == "300000.00"  # 500000 - 200000
        assert data["total_invoices"] == 1
        assert data["total_payments"] == 1
        assert data["total_expense_records"] == 1

    async def test_financial_summary_invalid_school(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test financial summary with invalid school."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/financial-summary",
            headers=auth_header(owner_token),
            params={
                "school_id": str(uuid.uuid4()),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today),
            },
        )

        assert response.status_code == 404

    async def test_financial_summary_invalid_date_range(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test financial summary with invalid date range."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/financial-summary",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today),
                "date_to": str(today - timedelta(days=30)),
            },
        )

        assert response.status_code == 400
        assert "date_to must be after date_from" in response.json()["detail"]


class TestPaymentReport:
    """Tests for payment report."""

    async def test_payment_report_empty(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test payment report with no data."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/payments",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_invoiced"] == "0"
        assert data["total_collected"] == "0"
        assert data["collection_rate"] == "0"

    async def test_payment_report_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        invoice: Invoice,
        payment: Payment,
    ):
        """Test payment report with data."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/payments",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today + timedelta(days=30)),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_invoiced"] == "1000000.00"
        assert data["total_collected"] == "500000.00"
        assert data["collection_rate"] == "50.00"
        assert data["invoice_status_counts"]["pending"] == 1

    async def test_payment_report_top_debtors(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        student: Student,
        school_class: SchoolClass,
    ):
        """Test payment report includes top debtors."""
        today = date.today()
        
        # Create an unpaid invoice
        invoice = Invoice(
            school_id=school.id,
            student_id=student.id,
            period_start=today.replace(day=1),
            period_end=(today.replace(day=1) + timedelta(days=30)),
            amount=Decimal("1000000.00"),
            discount_amount=Decimal("0"),
            due_date=today + timedelta(days=15),
            status=InvoiceStatus.PENDING,
        )
        db.add(invoice)
        await db.commit()

        response = await client.get(
            "/api/v1/reports/payments",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today + timedelta(days=30)),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["top_debtors"]) >= 1
        debtor = data["top_debtors"][0]
        assert debtor["student_name"] == "Ali Valiyev"
        assert debtor["outstanding"] == "1000000.00"


class TestExpenseReport:
    """Tests for expense report."""

    async def test_expense_report_empty(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test expense report with no data."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/expenses",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_expenses"] == "0"
        assert data["expense_count"] == 0
        assert data["by_category"] == []

    async def test_expense_report_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense: Expense,
        expense_category: ExpenseCategory,
    ):
        """Test expense report with data."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/expenses",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today + timedelta(days=1)),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_expenses"] == "200000.00"
        assert data["expense_count"] == 1
        assert len(data["by_category"]) == 1
        assert data["by_category"][0]["category_name"] == "Office Supplies"
        assert data["by_category"][0]["percentage_of_total"] == "100.00"

    async def test_expense_report_multiple_categories(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        owner_user,
    ):
        """Test expense report with multiple categories."""
        today = date.today()
        
        # Create another category
        utilities_cat = ExpenseCategory(name="Utilities", school_id=school.id)
        db.add(utilities_cat)
        await db.commit()
        await db.refresh(utilities_cat)

        # Create expenses
        exp1 = Expense(
            school_id=school.id,
            category_id=expense_category.id,
            amount=Decimal("300000"),
            expense_date=today,
            created_by_id=owner_user.id,
        )
        exp2 = Expense(
            school_id=school.id,
            category_id=utilities_cat.id,
            amount=Decimal("100000"),
            expense_date=today,
            created_by_id=owner_user.id,
        )
        db.add_all([exp1, exp2])
        await db.commit()

        response = await client.get(
            "/api/v1/reports/expenses",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=1)),
                "date_to": str(today + timedelta(days=1)),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_expenses"] == "400000.00"
        assert data["expense_count"] == 2
        assert len(data["by_category"]) == 2
        # Should be sorted by amount descending
        assert data["by_category"][0]["category_name"] == "Office Supplies"
        assert data["by_category"][0]["percentage_of_total"] == "75.00"
        assert data["by_category"][1]["category_name"] == "Utilities"
        assert data["by_category"][1]["percentage_of_total"] == "25.00"


class TestMonthlyTrend:
    """Tests for monthly trend report."""

    async def test_monthly_trend_empty(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test monthly trend with no data."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/monthly-trend",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=90)),
                "date_to": str(today),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["months"] == []

    async def test_monthly_trend_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        payment: Payment,
        expense: Expense,
    ):
        """Test monthly trend with data."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/monthly-trend",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today + timedelta(days=1)),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["months"]) >= 1
        # Current month should have our data
        current_month = today.strftime("%Y-%m")
        month_data = next((m for m in data["months"] if m["month"] == current_month), None)
        assert month_data is not None
        assert Decimal(month_data["income"]) == Decimal("500000.00")
        assert Decimal(month_data["expenses"]) == Decimal("200000.00")
        assert Decimal(month_data["net"]) == Decimal("300000.00")


class TestReportPermissions:
    """Tests for report permissions."""

    async def test_accountant_can_view_reports(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test that accountant level users can view reports."""
        today = date.today()
        response = await client.get(
            "/api/v1/reports/financial-summary",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "date_from": str(today - timedelta(days=30)),
                "date_to": str(today),
            },
        )

        assert response.status_code == 200
