"""Tests for Expenses API."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Employee, Expense, ExpenseCategory, Position
from app.models.school import School
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
async def position(db: AsyncSession, school: School) -> Position:
    """Create a test position."""
    position = Position(
        name="Teacher",
        school_id=school.id,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return position


@pytest.fixture
async def employee(db: AsyncSession, school: School, position: Position) -> Employee:
    """Create a test employee."""
    employee = Employee(
        school_id=school.id,
        position_id=position.id,
        first_name="John",
        last_name="Doe",
        salary=Decimal("5000000.00"),
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


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
        amount=Decimal("500000.00"),
        description="Office supplies purchase",
        expense_date=date.today(),
        created_by_id=owner_user.id,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


# ============== Tests ==============


class TestListExpenses:
    """Tests for listing expenses."""

    async def test_list_expenses_empty(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test listing expenses when none exist."""
        response = await client.get(
            "/api/v1/expenses",
            headers=auth_header(superuser_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_expenses_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        expense: Expense,
    ):
        """Test listing expenses with data."""
        response = await client.get(
            "/api/v1/expenses",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["amount"] == "500000.00"

    async def test_list_expenses_filter_by_category(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        owner_user,
    ):
        """Test filtering expenses by category."""
        # Create another category
        other_category = ExpenseCategory(name="Utilities", school_id=school.id)
        db.add(other_category)
        await db.commit()
        await db.refresh(other_category)

        # Create expenses
        exp1 = Expense(
            school_id=school.id,
            category_id=expense_category.id,
            amount=Decimal("100000"),
            expense_date=date.today(),
            created_by_id=owner_user.id,
        )
        exp2 = Expense(
            school_id=school.id,
            category_id=other_category.id,
            amount=Decimal("200000"),
            expense_date=date.today(),
            created_by_id=owner_user.id,
        )
        db.add_all([exp1, exp2])
        await db.commit()

        response = await client.get(
            "/api/v1/expenses",
            headers=auth_header(owner_token),
            params={"category_id": str(expense_category.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["category"]["name"] == "Office Supplies"

    async def test_list_expenses_filter_by_date(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        owner_user,
    ):
        """Test filtering expenses by date range."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        last_week = today - timedelta(days=7)

        # Create expenses
        exp1 = Expense(
            school_id=school.id,
            category_id=expense_category.id,
            amount=Decimal("100000"),
            expense_date=today,
            created_by_id=owner_user.id,
        )
        exp2 = Expense(
            school_id=school.id,
            category_id=expense_category.id,
            amount=Decimal("200000"),
            expense_date=last_week,
            created_by_id=owner_user.id,
        )
        db.add_all([exp1, exp2])
        await db.commit()

        response = await client.get(
            "/api/v1/expenses",
            headers=auth_header(owner_token),
            params={"date_from": str(yesterday)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["amount"] == "100000.00"


class TestCreateExpense:
    """Tests for creating expenses."""

    async def test_create_expense_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test successfully creating an expense."""
        expense_data = {
            "school_id": str(school.id),
            "category_id": str(expense_category.id),
            "amount": "750000.00",
            "description": "New printer",
            "expense_date": str(date.today()),
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["amount"] == "750000.00"
        assert data["description"] == "New printer"
        assert data["category"]["name"] == "Office Supplies"

    async def test_create_expense_with_employee(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        employee: Employee,
    ):
        """Test creating expense linked to employee (salary)."""
        expense_data = {
            "school_id": str(school.id),
            "category_id": str(expense_category.id),
            "employee_id": str(employee.id),
            "amount": "5000000.00",
            "description": "Salary payment",
            "expense_date": str(date.today()),
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["employee"]["first_name"] == "John"
        assert data["employee"]["last_name"] == "Doe"

    async def test_create_expense_invalid_school(
        self,
        client: AsyncClient,
        owner_token: str,
        expense_category: ExpenseCategory,
    ):
        """Test creating expense with invalid school."""
        expense_data = {
            "school_id": str(uuid.uuid4()),
            "category_id": str(expense_category.id),
            "amount": "100000.00",
            "expense_date": str(date.today()),
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "School not found"

    async def test_create_expense_invalid_category(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test creating expense with invalid category."""
        expense_data = {
            "school_id": str(school.id),
            "category_id": str(uuid.uuid4()),
            "amount": "100000.00",
            "expense_date": str(date.today()),
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Expense category not found"

    async def test_create_expense_invalid_employee(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test creating expense with invalid employee."""
        expense_data = {
            "school_id": str(school.id),
            "category_id": str(expense_category.id),
            "employee_id": str(uuid.uuid4()),
            "amount": "100000.00",
            "expense_date": str(date.today()),
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Employee not found"

    async def test_create_expense_negative_amount(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test creating expense with negative amount."""
        expense_data = {
            "school_id": str(school.id),
            "category_id": str(expense_category.id),
            "amount": "-100000.00",
            "expense_date": str(date.today()),
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 422


class TestGetExpense:
    """Tests for getting a single expense."""

    async def test_get_expense_success(
        self,
        client: AsyncClient,
        owner_token: str,
        expense: Expense,
    ):
        """Test successfully getting an expense."""
        response = await client.get(
            f"/api/v1/expenses/{expense.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(expense.id)
        assert data["amount"] == "500000.00"

    async def test_get_expense_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test getting non-existent expense."""
        response = await client.get(
            f"/api/v1/expenses/{uuid.uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Expense not found"


class TestUpdateExpense:
    """Tests for updating expenses."""

    async def test_update_expense_success(
        self,
        client: AsyncClient,
        owner_token: str,
        expense: Expense,
    ):
        """Test successfully updating an expense."""
        update_data = {
            "amount": "600000.00",
            "description": "Updated description",
        }

        response = await client.patch(
            f"/api/v1/expenses/{expense.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == "600000.00"
        assert data["description"] == "Updated description"

    async def test_update_expense_category(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense: Expense,
    ):
        """Test updating expense category."""
        # Create new category
        new_category = ExpenseCategory(name="Utilities", school_id=school.id)
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)

        update_data = {"category_id": str(new_category.id)}

        response = await client.patch(
            f"/api/v1/expenses/{expense.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["category"]["name"] == "Utilities"

    async def test_update_expense_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test updating non-existent expense."""
        response = await client.patch(
            f"/api/v1/expenses/{uuid.uuid4()}",
            json={"amount": "100000"},
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404

    async def test_update_expense_invalid_category(
        self,
        client: AsyncClient,
        owner_token: str,
        expense: Expense,
    ):
        """Test updating expense with invalid category."""
        response = await client.patch(
            f"/api/v1/expenses/{expense.id}",
            json={"category_id": str(uuid.uuid4())},
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Expense category not found"


class TestDeleteExpense:
    """Tests for deleting expenses."""

    async def test_delete_expense_success(
        self,
        client: AsyncClient,
        owner_token: str,
        expense: Expense,
    ):
        """Test successfully deleting an expense."""
        response = await client.delete(
            f"/api/v1/expenses/{expense.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 204

        # Verify deleted
        get_response = await client.get(
            f"/api/v1/expenses/{expense.id}",
            headers=auth_header(owner_token),
        )
        assert get_response.status_code == 404

    async def test_delete_expense_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test deleting non-existent expense."""
        response = await client.delete(
            f"/api/v1/expenses/{uuid.uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestExpenseSummary:
    """Tests for expense summary."""

    async def test_get_summary(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
        owner_user,
    ):
        """Test getting expense summary."""
        # Create another category
        other_category = ExpenseCategory(name="Utilities", school_id=school.id)
        db.add(other_category)
        await db.commit()
        await db.refresh(other_category)

        # Create expenses
        exp1 = Expense(
            school_id=school.id,
            category_id=expense_category.id,
            amount=Decimal("100000"),
            expense_date=date.today(),
            created_by_id=owner_user.id,
        )
        exp2 = Expense(
            school_id=school.id,
            category_id=other_category.id,
            amount=Decimal("200000"),
            expense_date=date.today(),
            created_by_id=owner_user.id,
        )
        db.add_all([exp1, exp2])
        await db.commit()

        response = await client.get(
            f"/api/v1/expenses/summary?school_id={school.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_expenses"] == 2
        assert data["total_amount"] == "300000.00"
        assert "Office Supplies" in data["by_category"]
        assert "Utilities" in data["by_category"]

    async def test_get_summary_invalid_school(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test getting summary for invalid school."""
        response = await client.get(
            f"/api/v1/expenses/summary?school_id={uuid.uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestSQLInjection:
    """Tests for SQL injection prevention."""

    async def test_create_expense_sql_injection(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test that description field is safe from SQL injection."""
        expense_data = {
            "school_id": str(school.id),
            "category_id": str(expense_category.id),
            "amount": "100000.00",
            "description": "Test'); DROP TABLE expenses; --",
            "expense_date": str(date.today()),
        }

        response = await client.post(
            "/api/v1/expenses",
            json=expense_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 201
        # The injection attempt should be stored as literal text
        assert "DROP TABLE" in response.json()["description"]
