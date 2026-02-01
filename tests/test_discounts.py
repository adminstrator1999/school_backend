"""Tests for Discounts API."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import Discount, DiscountType, StudentDiscount
from app.models.school import School
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
async def discount(db: AsyncSession, school: School) -> Discount:
    """Create a test discount."""
    discount = Discount(
        school_id=school.id,
        name="Sibling Discount",
        type=DiscountType.PERCENTAGE,
        value=Decimal("10.00"),
    )
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return discount


@pytest.fixture
async def fixed_discount(db: AsyncSession, school: School) -> Discount:
    """Create a fixed amount discount."""
    discount = Discount(
        school_id=school.id,
        name="Early Payment Discount",
        type=DiscountType.FIXED,
        value=Decimal("50000.00"),
    )
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return discount


@pytest.fixture
async def student(db: AsyncSession, school: School) -> Student:
    """Create a test student."""
    student = Student(
        school_id=school.id,
        first_name="Test",
        last_name="Student",
        phone="+998901234567",
        parent_first_name="Parent",
        parent_last_name="Test",
        parent_phone_1="+998909876543",
        monthly_fee=Decimal("1000000.00"),
        payment_day=1,
        enrolled_at=date.today(),
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


# ============== Discount CRUD Tests ==============


class TestListDiscounts:
    """Tests for listing discounts."""

    async def test_list_discounts_empty(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test listing discounts when none exist."""
        response = await client.get(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_discounts_with_data(
        self,
        client: AsyncClient,
        owner_token: str,
        discount: Discount,
        fixed_discount: Discount,
    ):
        """Test listing discounts with data."""
        response = await client.get(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = [d["name"] for d in data["items"]]
        assert "Sibling Discount" in names
        assert "Early Payment Discount" in names

    async def test_list_discounts_filter_by_type(
        self,
        client: AsyncClient,
        owner_token: str,
        discount: Discount,
        fixed_discount: Discount,
    ):
        """Test filtering discounts by type."""
        response = await client.get(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            params={"type": "percentage"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Sibling Discount"
        assert data["items"][0]["type"] == "percentage"

    async def test_list_discounts_search(
        self,
        client: AsyncClient,
        owner_token: str,
        discount: Discount,
        fixed_discount: Discount,
    ):
        """Test searching discounts by name."""
        response = await client.get(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            params={"search": "sibling"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Sibling Discount"


class TestCreateDiscount:
    """Tests for creating discounts."""

    async def test_create_percentage_discount(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test creating a percentage discount."""
        response = await client.post(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "name": "Staff Child Discount",
                "type": "percentage",
                "value": "25.00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Staff Child Discount"
        assert data["type"] == "percentage"
        assert data["value"] == "25.00"
        assert data["is_active"] is True

    async def test_create_fixed_discount(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test creating a fixed amount discount."""
        response = await client.post(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "name": "Scholarship",
                "type": "fixed",
                "value": "500000.00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Scholarship"
        assert data["type"] == "fixed"
        assert data["value"] == "500000.00"

    async def test_create_discount_with_dates(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test creating a discount with validity dates."""
        today = date.today()
        end_date = today + timedelta(days=30)

        response = await client.post(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "name": "Seasonal Discount",
                "type": "percentage",
                "value": "15.00",
                "valid_from": str(today),
                "valid_until": str(end_date),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["valid_from"] == str(today)
        assert data["valid_until"] == str(end_date)

    async def test_create_discount_invalid_school(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test creating discount with non-existent school."""
        response = await client.post(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            json={
                "school_id": str(uuid4()),
                "name": "Test Discount",
                "type": "percentage",
                "value": "10.00",
            },
        )

        assert response.status_code == 404
        assert "School not found" in response.json()["detail"]

    async def test_create_percentage_discount_over_100(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test that percentage discount cannot exceed 100%."""
        response = await client.post(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "name": "Invalid Discount",
                "type": "percentage",
                "value": "150.00",
            },
        )

        assert response.status_code == 422

    async def test_create_discount_invalid_date_range(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test that valid_from must be before valid_until."""
        today = date.today()
        yesterday = today - timedelta(days=1)

        response = await client.post(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "name": "Invalid Dates Discount",
                "type": "percentage",
                "value": "10.00",
                "valid_from": str(today),
                "valid_until": str(yesterday),
            },
        )

        assert response.status_code == 400
        assert "valid_from must be before valid_until" in response.json()["detail"]


class TestGetDiscount:
    """Tests for getting a single discount."""

    async def test_get_discount_success(
        self,
        client: AsyncClient,
        owner_token: str,
        discount: Discount,
    ):
        """Test getting a discount by ID."""
        response = await client.get(
            f"/api/v1/discounts/{discount.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(discount.id)
        assert data["name"] == "Sibling Discount"

    async def test_get_discount_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test getting a non-existent discount."""
        response = await client.get(
            f"/api/v1/discounts/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestUpdateDiscount:
    """Tests for updating discounts."""

    async def test_update_discount_success(
        self,
        client: AsyncClient,
        owner_token: str,
        discount: Discount,
    ):
        """Test updating a discount."""
        response = await client.patch(
            f"/api/v1/discounts/{discount.id}",
            headers=auth_header(owner_token),
            json={"name": "Updated Sibling Discount", "value": "15.00"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Sibling Discount"
        assert data["value"] == "15.00"

    async def test_update_discount_type(
        self,
        client: AsyncClient,
        owner_token: str,
        discount: Discount,
    ):
        """Test updating discount type."""
        response = await client.patch(
            f"/api/v1/discounts/{discount.id}",
            headers=auth_header(owner_token),
            json={"type": "fixed", "value": "100000.00"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "fixed"
        assert data["value"] == "100000.00"

    async def test_update_discount_deactivate(
        self,
        client: AsyncClient,
        owner_token: str,
        discount: Discount,
    ):
        """Test deactivating a discount."""
        response = await client.patch(
            f"/api/v1/discounts/{discount.id}",
            headers=auth_header(owner_token),
            json={"is_active": False},
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    async def test_update_discount_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test updating a non-existent discount."""
        response = await client.patch(
            f"/api/v1/discounts/{uuid4()}",
            headers=auth_header(owner_token),
            json={"name": "Updated"},
        )

        assert response.status_code == 404


class TestDeleteDiscount:
    """Tests for deleting discounts."""

    async def test_delete_discount_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        discount: Discount,
    ):
        """Test soft deleting a discount."""
        response = await client.delete(
            f"/api/v1/discounts/{discount.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 204

        # Verify it's deactivated
        await db.refresh(discount)
        assert discount.is_active is False

    async def test_delete_discount_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test deleting a non-existent discount."""
        response = await client.delete(
            f"/api/v1/discounts/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


# ============== Student Discount Assignment Tests ==============


class TestStudentDiscounts:
    """Tests for student discount assignments."""

    async def test_get_student_discounts_empty(
        self,
        client: AsyncClient,
        owner_token: str,
        student: Student,
    ):
        """Test getting discounts for a student with none assigned."""
        response = await client.get(
            f"/api/v1/discounts/students/{student.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == str(student.id)
        assert data["discounts"] == []

    async def test_assign_discount_to_student(
        self,
        client: AsyncClient,
        owner_token: str,
        student: Student,
        discount: Discount,
    ):
        """Test assigning a discount to a student."""
        response = await client.post(
            "/api/v1/discounts/students",
            headers=auth_header(owner_token),
            json={
                "student_id": str(student.id),
                "discount_id": str(discount.id),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["student_id"] == str(student.id)
        assert data["discount_id"] == str(discount.id)
        assert data["discount"]["name"] == "Sibling Discount"

    async def test_assign_multiple_discounts(
        self,
        client: AsyncClient,
        owner_token: str,
        student: Student,
        discount: Discount,
        fixed_discount: Discount,
    ):
        """Test assigning multiple discounts to a student."""
        # Assign first discount
        await client.post(
            "/api/v1/discounts/students",
            headers=auth_header(owner_token),
            json={
                "student_id": str(student.id),
                "discount_id": str(discount.id),
            },
        )

        # Assign second discount
        await client.post(
            "/api/v1/discounts/students",
            headers=auth_header(owner_token),
            json={
                "student_id": str(student.id),
                "discount_id": str(fixed_discount.id),
            },
        )

        # Get all discounts
        response = await client.get(
            f"/api/v1/discounts/students/{student.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["discounts"]) == 2

    async def test_assign_duplicate_discount(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        student: Student,
        discount: Discount,
    ):
        """Test that duplicate discount assignment is rejected."""
        # Assign first time
        assignment = StudentDiscount(
            student_id=student.id,
            discount_id=discount.id,
        )
        db.add(assignment)
        await db.commit()

        # Try to assign again
        response = await client.post(
            "/api/v1/discounts/students",
            headers=auth_header(owner_token),
            json={
                "student_id": str(student.id),
                "discount_id": str(discount.id),
            },
        )

        assert response.status_code == 400
        assert "already assigned" in response.json()["detail"]

    async def test_assign_discount_student_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
        discount: Discount,
    ):
        """Test assigning discount to non-existent student."""
        response = await client.post(
            "/api/v1/discounts/students",
            headers=auth_header(owner_token),
            json={
                "student_id": str(uuid4()),
                "discount_id": str(discount.id),
            },
        )

        assert response.status_code == 404
        assert "Student not found" in response.json()["detail"]

    async def test_assign_discount_not_found(
        self,
        client: AsyncClient,
        owner_token: str,
        student: Student,
    ):
        """Test assigning non-existent discount to student."""
        response = await client.post(
            "/api/v1/discounts/students",
            headers=auth_header(owner_token),
            json={
                "student_id": str(student.id),
                "discount_id": str(uuid4()),
            },
        )

        assert response.status_code == 404
        assert "Discount not found" in response.json()["detail"]

    async def test_assign_discount_different_school(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        student: Student,
    ):
        """Test that discount and student must be in the same school."""
        # Create another school with its own discount
        other_school = School(name="Other School")
        db.add(other_school)
        await db.commit()
        await db.refresh(other_school)

        other_discount = Discount(
            school_id=other_school.id,
            name="Other Discount",
            type=DiscountType.PERCENTAGE,
            value=Decimal("10.00"),
        )
        db.add(other_discount)
        await db.commit()
        await db.refresh(other_discount)

        response = await client.post(
            "/api/v1/discounts/students",
            headers=auth_header(owner_token),
            json={
                "student_id": str(student.id),
                "discount_id": str(other_discount.id),
            },
        )

        assert response.status_code == 400
        assert "same school" in response.json()["detail"]

    async def test_remove_discount_from_student(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
        student: Student,
        discount: Discount,
    ):
        """Test removing a discount from a student."""
        # First assign the discount
        assignment = StudentDiscount(
            student_id=student.id,
            discount_id=discount.id,
        )
        db.add(assignment)
        await db.commit()

        # Remove the discount
        response = await client.delete(
            f"/api/v1/discounts/students/{student.id}/discounts/{discount.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 204

        # Verify it's removed
        get_response = await client.get(
            f"/api/v1/discounts/students/{student.id}",
            headers=auth_header(owner_token),
        )
        assert get_response.json()["discounts"] == []

    async def test_remove_discount_not_assigned(
        self,
        client: AsyncClient,
        owner_token: str,
        student: Student,
        discount: Discount,
    ):
        """Test removing a discount that was never assigned."""
        response = await client.delete(
            f"/api/v1/discounts/students/{student.id}/discounts/{discount.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
        assert "assignment not found" in response.json()["detail"]


# ============== SQL Injection Tests ==============


class TestSQLInjection:
    """Tests for SQL injection protection."""

    async def test_search_sql_injection(
        self,
        client: AsyncClient,
        owner_token: str,
    ):
        """Test that search is protected against SQL injection."""
        response = await client.get(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            params={"search": "'; DROP TABLE discounts; --"},
        )

        assert response.status_code == 200

    async def test_create_discount_sql_injection(
        self,
        client: AsyncClient,
        owner_token: str,
        school: School,
    ):
        """Test that name field is protected against SQL injection."""
        response = await client.post(
            "/api/v1/discounts",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "name": "'; DROP TABLE discounts; --",
                "type": "percentage",
                "value": "10.00",
            },
        )

        assert response.status_code == 201
        assert response.json()["name"] == "'; DROP TABLE discounts; --"
