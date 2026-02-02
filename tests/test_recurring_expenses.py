"""Tests for Recurring Expenses API."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import ExpenseCategory, RecurringExpense, RecurrenceType, Expense
from app.models.school import School


def auth_header(token: str) -> dict:
    """Create auth header."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def school(db: AsyncSession) -> School:
    """Create a test school."""
    school = School(
        name="Test School",
        address="123 Test St",
        phone="+998901234567",
    )
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


@pytest.fixture
async def expense_category(db: AsyncSession, school: School) -> ExpenseCategory:
    """Create a test expense category."""
    category = ExpenseCategory(
        school_id=school.id,
        name="Utilities",
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@pytest.fixture
async def recurring_expense(
    db: AsyncSession, school: School, expense_category: ExpenseCategory
) -> RecurringExpense:
    """Create a test recurring expense."""
    recurring = RecurringExpense(
        school_id=school.id,
        category_id=expense_category.id,
        name="Monthly Electricity",
        amount=Decimal("500000.00"),
        recurrence=RecurrenceType.MONTHLY,
        day_of_month=15,
        is_active=True,
    )
    db.add(recurring)
    await db.commit()
    await db.refresh(recurring)
    return recurring


class TestListRecurringExpenses:
    """Tests for listing recurring expenses."""

    async def test_list_recurring_expenses_empty(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test listing recurring expenses when none exist."""
        response = await client.get(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            params={"school_id": str(school.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_recurring_expenses_with_data(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        recurring_expense: RecurringExpense,
    ):
        """Test listing recurring expenses with data."""
        response = await client.get(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            params={"school_id": str(school.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Monthly Electricity"
        assert data["items"][0]["category_name"] == "Utilities"

    async def test_list_recurring_expenses_filter_active(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        db: AsyncSession,
    ):
        """Test filtering recurring expenses by active status."""
        # Create active and inactive recurring expenses
        active = RecurringExpense(
            school_id=school.id,
            category_id=expense_category.id,
            name="Active Expense",
            amount=Decimal("100000.00"),
            recurrence=RecurrenceType.MONTHLY,
            day_of_month=1,
            is_active=True,
        )
        inactive = RecurringExpense(
            school_id=school.id,
            category_id=expense_category.id,
            name="Inactive Expense",
            amount=Decimal("200000.00"),
            recurrence=RecurrenceType.MONTHLY,
            day_of_month=1,
            is_active=False,
        )
        db.add_all([active, inactive])
        await db.commit()

        # Filter active only
        response = await client.get(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            params={"school_id": str(school.id), "is_active": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Active Expense"

    async def test_list_recurring_expenses_search(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        recurring_expense: RecurringExpense,
    ):
        """Test searching recurring expenses by name."""
        response = await client.get(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            params={"school_id": str(school.id), "search": "Electricity"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "Electricity" in data["items"][0]["name"]


class TestCreateRecurringExpense:
    """Tests for creating recurring expenses."""

    async def test_create_recurring_expense_success(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test successful recurring expense creation."""
        response = await client.post(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "category_id": str(expense_category.id),
                "name": "Monthly Rent",
                "amount": "5000000.00",
                "recurrence": "monthly",
                "day_of_month": 1,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Monthly Rent"
        assert Decimal(data["amount"]) == Decimal("5000000.00")
        assert data["recurrence"] == "monthly"
        assert data["day_of_month"] == 1
        assert data["is_active"] is True

    async def test_create_recurring_expense_quarterly(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test creating a quarterly recurring expense."""
        response = await client.post(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "category_id": str(expense_category.id),
                "name": "Quarterly Insurance",
                "amount": "2000000.00",
                "recurrence": "quarterly",
                "day_of_month": 15,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["recurrence"] == "quarterly"

    async def test_create_recurring_expense_yearly(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test creating a yearly recurring expense."""
        response = await client.post(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "category_id": str(expense_category.id),
                "name": "Annual License",
                "amount": "10000000.00",
                "recurrence": "yearly",
                "day_of_month": 1,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["recurrence"] == "yearly"

    async def test_create_recurring_expense_invalid_school(
        self,
        client: AsyncClient,
        owner_token: str,
        expense_category: ExpenseCategory,
    ):
        """Test creating recurring expense with invalid school."""
        response = await client.post(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            json={
                "school_id": str(uuid4()),
                "category_id": str(expense_category.id),
                "name": "Test",
                "amount": "100000.00",
                "recurrence": "monthly",
                "day_of_month": 1,
            },
        )
        assert response.status_code == 404
        assert "School not found" in response.json()["detail"]

    async def test_create_recurring_expense_invalid_category(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test creating recurring expense with invalid category."""
        response = await client.post(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "category_id": str(uuid4()),
                "name": "Test",
                "amount": "100000.00",
                "recurrence": "monthly",
                "day_of_month": 1,
            },
        )
        assert response.status_code == 404
        assert "category not found" in response.json()["detail"]

    async def test_create_recurring_expense_invalid_day(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test creating recurring expense with invalid day of month."""
        response = await client.post(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "category_id": str(expense_category.id),
                "name": "Test",
                "amount": "100000.00",
                "recurrence": "monthly",
                "day_of_month": 32,
            },
        )
        assert response.status_code == 422


class TestGetRecurringExpense:
    """Tests for getting a single recurring expense."""

    async def test_get_recurring_expense_success(
        self,
        client: AsyncClient,
        owner_token: str,
        recurring_expense: RecurringExpense,
    ):
        """Test successful retrieval of a recurring expense."""
        response = await client.get(
            f"/api/v1/recurring-expenses/{recurring_expense.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(recurring_expense.id)
        assert data["name"] == recurring_expense.name

    async def test_get_recurring_expense_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test retrieving non-existent recurring expense."""
        response = await client.get(
            f"/api/v1/recurring-expenses/{uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestUpdateRecurringExpense:
    """Tests for updating recurring expenses."""

    async def test_update_recurring_expense_success(
        self,
        client: AsyncClient,
        owner_token: str,
        recurring_expense: RecurringExpense,
    ):
        """Test successful update of a recurring expense."""
        response = await client.patch(
            f"/api/v1/recurring-expenses/{recurring_expense.id}",
            headers=auth_header(owner_token),
            json={"name": "Updated Electricity Bill", "amount": "600000.00"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Electricity Bill"
        assert Decimal(data["amount"]) == Decimal("600000.00")

    async def test_update_recurring_expense_deactivate(
        self,
        client: AsyncClient,
        owner_token: str,
        recurring_expense: RecurringExpense,
    ):
        """Test deactivating a recurring expense."""
        response = await client.patch(
            f"/api/v1/recurring-expenses/{recurring_expense.id}",
            headers=auth_header(owner_token),
            json={"is_active": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    async def test_update_recurring_expense_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test updating non-existent recurring expense."""
        response = await client.patch(
            f"/api/v1/recurring-expenses/{uuid4()}",
            headers=auth_header(owner_token),
            json={"name": "Test"},
        )
        assert response.status_code == 404


class TestDeleteRecurringExpense:
    """Tests for deleting recurring expenses."""

    async def test_delete_recurring_expense_success(
        self,
        client: AsyncClient,
        owner_token: str,
        recurring_expense: RecurringExpense,
    ):
        """Test successful deletion of a recurring expense."""
        response = await client.delete(
            f"/api/v1/recurring-expenses/{recurring_expense.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 204

        # Verify deletion
        response = await client.get(
            f"/api/v1/recurring-expenses/{recurring_expense.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404

    async def test_delete_recurring_expense_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test deleting non-existent recurring expense."""
        response = await client.delete(
            f"/api/v1/recurring-expenses/{uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestGenerateExpenses:
    """Tests for generating expenses from recurring templates."""

    async def test_generate_expenses_success(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        db: AsyncSession,
    ):
        """Test successful expense generation from recurring template."""
        today = date.today()
        
        # Create recurring expense due today
        recurring = RecurringExpense(
            school_id=school.id,
            category_id=expense_category.id,
            name="Due Today",
            amount=Decimal("100000.00"),
            recurrence=RecurrenceType.MONTHLY,
            day_of_month=today.day,
            is_active=True,
        )
        db.add(recurring)
        await db.commit()

        response = await client.post(
            "/api/v1/recurring-expenses/generate",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "target_date": str(today),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 1
        assert len(data["expenses"]) == 1
        assert "Successfully generated" in data["message"]

    async def test_generate_expenses_no_due(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        db: AsyncSession,
    ):
        """Test expense generation when no templates are due."""
        today = date.today()
        different_day = (today.day % 28) + 1  # Different day

        # Create recurring expense not due today
        recurring = RecurringExpense(
            school_id=school.id,
            category_id=expense_category.id,
            name="Not Due Today",
            amount=Decimal("100000.00"),
            recurrence=RecurrenceType.MONTHLY,
            day_of_month=different_day,
            is_active=True,
        )
        db.add(recurring)
        await db.commit()

        response = await client.post(
            "/api/v1/recurring-expenses/generate",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "target_date": str(today),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 0
        assert "No recurring expenses due" in data["message"]

    async def test_generate_expenses_skips_already_generated(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        db: AsyncSession,
    ):
        """Test that already generated expenses are not duplicated."""
        today = date.today()

        # Create recurring expense that was already generated this month
        recurring = RecurringExpense(
            school_id=school.id,
            category_id=expense_category.id,
            name="Already Generated",
            amount=Decimal("100000.00"),
            recurrence=RecurrenceType.MONTHLY,
            day_of_month=today.day,
            is_active=True,
            last_generated_at=today,  # Already generated today
        )
        db.add(recurring)
        await db.commit()

        response = await client.post(
            "/api/v1/recurring-expenses/generate",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "target_date": str(today),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 0

    async def test_generate_expenses_invalid_school(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test generating expenses for invalid school."""
        response = await client.post(
            "/api/v1/recurring-expenses/generate",
            headers=auth_header(owner_token),
            json={
                "school_id": str(uuid4()),
            },
        )
        assert response.status_code == 404


class TestGetDueRecurringExpenses:
    """Tests for getting due recurring expenses."""

    async def test_get_due_recurring_expenses(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        db: AsyncSession,
    ):
        """Test getting recurring expenses due on a specific date."""
        today = date.today()

        # Create recurring expense due today
        due_expense = RecurringExpense(
            school_id=school.id,
            category_id=expense_category.id,
            name="Due Expense",
            amount=Decimal("100000.00"),
            recurrence=RecurrenceType.MONTHLY,
            day_of_month=today.day,
            is_active=True,
        )
        
        # Create recurring expense not due today
        not_due_expense = RecurringExpense(
            school_id=school.id,
            category_id=expense_category.id,
            name="Not Due Expense",
            amount=Decimal("200000.00"),
            recurrence=RecurrenceType.MONTHLY,
            day_of_month=(today.day % 28) + 1,
            is_active=True,
        )
        
        db.add_all([due_expense, not_due_expense])
        await db.commit()

        response = await client.get(
            f"/api/v1/recurring-expenses/due/{school.id}",
            headers=auth_header(owner_token),
            params={"target_date": str(today)},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Due Expense"


class TestRecurringExpensePermissions:
    """Tests for recurring expense permissions."""

    async def test_staff_cannot_manage_recurring_expenses(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        db: AsyncSession,
    ):
        """Test that staff users cannot manage recurring expenses."""
        from app.models.user import User
        from app.core.permissions import Role
        from app.core.security import get_password_hash

        # Create staff user
        staff = User(
            phone_number="+998901112233",
            password_hash=get_password_hash("password123"),
            role=Role.STAFF,
            school_id=school.id,
            first_name="Staff",
            last_name="User",
        )
        db.add(staff)
        await db.commit()
        await db.refresh(staff)

        # Login to get token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "+998901112233", "password": "password123"},
        )
        staff_token = login_response.json()["access_token"]

        # Try to list recurring expenses
        response = await client.get(
            "/api/v1/recurring-expenses",
            headers=auth_header(staff_token),
        )
        assert response.status_code == 403

    async def test_accountant_can_manage_recurring_expenses(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        db: AsyncSession,
    ):
        """Test that accountants can manage recurring expenses."""
        from app.models.user import User
        from app.core.permissions import Role
        from app.core.security import get_password_hash

        # Create accountant user
        accountant = User(
            phone_number="+998901112244",
            password_hash=get_password_hash("password123"),
            role=Role.ACCOUNTANT,
            school_id=school.id,
            first_name="Accountant",
            last_name="User",
        )
        db.add(accountant)
        await db.commit()
        await db.refresh(accountant)

        # Login to get token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "+998901112244", "password": "password123"},
        )
        accountant_token = login_response.json()["access_token"]

        # Create recurring expense
        response = await client.post(
            "/api/v1/recurring-expenses",
            headers=auth_header(accountant_token),
            json={
                "school_id": str(school.id),
                "category_id": str(expense_category.id),
                "name": "Accountant Created",
                "amount": "100000.00",
                "recurrence": "monthly",
                "day_of_month": 1,
            },
        )
        assert response.status_code == 201


class TestSQLInjection:
    """Tests for SQL injection prevention."""

    async def test_search_sql_injection(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test that search parameter is safe from SQL injection."""
        response = await client.get(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            params={
                "school_id": str(school.id),
                "search": "'; DROP TABLE recurring_expenses; --",
            },
        )
        assert response.status_code == 200

    async def test_create_sql_injection_in_name(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test that name field is safe from SQL injection."""
        response = await client.post(
            "/api/v1/recurring-expenses",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "category_id": str(expense_category.id),
                "name": "Test'; DROP TABLE recurring_expenses; --",
                "amount": "100000.00",
                "recurrence": "monthly",
                "day_of_month": 1,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "DROP TABLE" in data["name"]  # Stored as plain text, not executed
