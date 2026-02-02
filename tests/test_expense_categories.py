"""Tests for Expense Categories API."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import ExpenseCategory
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
        name="Salaries",
        school_id=school.id,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@pytest.fixture
async def system_category(db: AsyncSession) -> ExpenseCategory:
    """Create a system-wide expense category."""
    category = ExpenseCategory(
        name="Utilities",
        is_system=True,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


# ============== Tests ==============


class TestListExpenseCategories:
    """Tests for listing expense categories."""

    async def test_list_categories_empty(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test listing expense categories when none exist."""
        response = await client.get(
            "/api/v1/expense-categories",
            headers=auth_header(superuser_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_categories_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        superuser_token: str,
        school: School,
    ):
        """Test listing expense categories with data."""
        # Create system category
        system_cat = ExpenseCategory(name="General", is_system=True)
        # Create school category
        school_cat = ExpenseCategory(name="Supplies", school_id=school.id)
        db.add_all([system_cat, school_cat])
        await db.commit()

        response = await client.get(
            "/api/v1/expense-categories",
            headers=auth_header(superuser_token),
            params={"school_id": str(school.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # System + school category
        names = [c["name"] for c in data["items"]]
        assert "General" in names
        assert "Supplies" in names

    async def test_list_categories_filter_by_school(
        self,
        client: AsyncClient,
        db: AsyncSession,
        superuser_token: str,
        school: School,
    ):
        """Test filtering expense categories by school."""
        # Create categories for different schools
        other_school = School(name="Other School")
        db.add(other_school)
        await db.commit()
        await db.refresh(other_school)

        cat1 = ExpenseCategory(name="Cat 1", school_id=school.id)
        cat2 = ExpenseCategory(name="Cat 2", school_id=other_school.id)
        db.add_all([cat1, cat2])
        await db.commit()

        response = await client.get(
            "/api/v1/expense-categories",
            headers=auth_header(superuser_token),
            params={"school_id": str(school.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Cat 1"

    async def test_list_categories_search(
        self,
        client: AsyncClient,
        db: AsyncSession,
        superuser_token: str,
        school: School,
    ):
        """Test searching expense categories by name."""
        cat1 = ExpenseCategory(name="Salaries", school_id=school.id)
        cat2 = ExpenseCategory(name="Supplies", school_id=school.id)
        db.add_all([cat1, cat2])
        await db.commit()

        response = await client.get(
            "/api/v1/expense-categories",
            headers=auth_header(superuser_token),
            params={"search": "sal"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Salaries"


class TestCreateExpenseCategory:
    """Tests for creating expense categories."""

    async def test_create_category_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
    ):
        """Test successfully creating an expense category."""
        category_data = {
            "school_id": str(school.id),
            "name": "Office Supplies",
        }

        response = await client.post(
            "/api/v1/expense-categories",
            json=category_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Office Supplies"
        assert data["school_id"] == str(school.id)
        assert data["is_system"] is False

    async def test_create_category_trims_whitespace(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
    ):
        """Test that category name is trimmed."""
        category_data = {
            "school_id": str(school.id),
            "name": "  Office Supplies  ",
        }

        response = await client.post(
            "/api/v1/expense-categories",
            json=category_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Office Supplies"

    async def test_create_category_invalid_school(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test creating category with invalid school ID."""
        category_data = {
            "school_id": str(uuid.uuid4()),
            "name": "Test Category",
        }

        response = await client.post(
            "/api/v1/expense-categories",
            json=category_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "School not found"

    async def test_create_category_duplicate_name(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test creating category with duplicate name."""
        category_data = {
            "school_id": str(school.id),
            "name": expense_category.name,
        }

        response = await client.post(
            "/api/v1/expense-categories",
            json=category_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    async def test_create_category_duplicate_name_case_insensitive(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
        expense_category: ExpenseCategory,
    ):
        """Test that duplicate check is case insensitive."""
        category_data = {
            "school_id": str(school.id),
            "name": expense_category.name.upper(),
        }

        response = await client.post(
            "/api/v1/expense-categories",
            json=category_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 409


class TestGetExpenseCategory:
    """Tests for getting a single expense category."""

    async def test_get_category_success(
        self,
        client: AsyncClient,
        owner_token: str,
        expense_category: ExpenseCategory,
    ):
        """Test successfully getting an expense category."""
        response = await client.get(
            f"/api/v1/expense-categories/{expense_category.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(expense_category.id)
        assert data["name"] == expense_category.name

    async def test_get_category_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test getting non-existent expense category."""
        response = await client.get(
            f"/api/v1/expense-categories/{uuid.uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Expense category not found"

    async def test_get_system_category(
        self,
        client: AsyncClient,
        owner_token: str,
        system_category: ExpenseCategory,
    ):
        """Test getting a system expense category."""
        response = await client.get(
            f"/api/v1/expense-categories/{system_category.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_system"] is True


class TestUpdateExpenseCategory:
    """Tests for updating expense categories."""

    async def test_update_category_success(
        self,
        client: AsyncClient,
        owner_token: str,
        expense_category: ExpenseCategory,
    ):
        """Test successfully updating an expense category."""
        update_data = {"name": "Updated Salaries"}

        response = await client.patch(
            f"/api/v1/expense-categories/{expense_category.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Salaries"

    async def test_update_category_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test updating non-existent expense category."""
        response = await client.patch(
            f"/api/v1/expense-categories/{uuid.uuid4()}",
            json={"name": "New Name"},
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404

    async def test_update_system_category_forbidden(
        self,
        client: AsyncClient,
        owner_token: str,
        system_category: ExpenseCategory,
    ):
        """Test that system categories cannot be updated."""
        response = await client.patch(
            f"/api/v1/expense-categories/{system_category.id}",
            json={"name": "New Name"},
            headers=auth_header(owner_token),
        )

        assert response.status_code == 403
        assert "system" in response.json()["detail"].lower()

    async def test_update_category_duplicate_name(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
    ):
        """Test updating category to duplicate name."""
        cat1 = ExpenseCategory(name="Category 1", school_id=school.id)
        cat2 = ExpenseCategory(name="Category 2", school_id=school.id)
        db.add_all([cat1, cat2])
        await db.commit()
        await db.refresh(cat1)
        await db.refresh(cat2)

        response = await client.patch(
            f"/api/v1/expense-categories/{cat2.id}",
            json={"name": "Category 1"},
            headers=auth_header(owner_token),
        )

        assert response.status_code == 409


class TestDeleteExpenseCategory:
    """Tests for deleting expense categories."""

    async def test_delete_category_success(
        self,
        client: AsyncClient,
        owner_token: str,
        expense_category: ExpenseCategory,
    ):
        """Test successfully deleting an expense category."""
        response = await client.delete(
            f"/api/v1/expense-categories/{expense_category.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 204

        # Verify deleted
        get_response = await client.get(
            f"/api/v1/expense-categories/{expense_category.id}",
            headers=auth_header(owner_token),
        )
        assert get_response.status_code == 404

    async def test_delete_category_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test deleting non-existent expense category."""
        response = await client.delete(
            f"/api/v1/expense-categories/{uuid.uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404

    async def test_delete_system_category_forbidden(
        self,
        client: AsyncClient,
        owner_token: str,
        system_category: ExpenseCategory,
    ):
        """Test that system categories cannot be deleted."""
        response = await client.delete(
            f"/api/v1/expense-categories/{system_category.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 403
        assert "system" in response.json()["detail"].lower()


class TestSQLInjection:
    """Tests for SQL injection prevention."""

    async def test_search_sql_injection(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test that search parameter is safe from SQL injection."""
        response = await client.get(
            "/api/v1/expense-categories",
            headers=auth_header(owner_token),
            params={"search": "'; DROP TABLE expense_categories; --"},
        )

        assert response.status_code == 200

    async def test_create_category_sql_injection(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        school: School,
    ):
        """Test that name field is safe from SQL injection."""
        category_data = {
            "school_id": str(school.id),
            "name": "Test'); DROP TABLE expense_categories; --",
        }

        response = await client.post(
            "/api/v1/expense-categories",
            json=category_data,
            headers=auth_header(owner_token),
        )

        assert response.status_code == 201
        # The injection attempt should be stored as literal text
        assert "DROP TABLE" in response.json()["name"]
