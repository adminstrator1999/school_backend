"""Tests for students API."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.models.school_class import SchoolClass
from app.models.student import Student
from tests.conftest import auth_header


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
    """Create a test school class."""
    school_class = SchoolClass(
        school_id=school.id,
        grade=1,
        section="A",
    )
    db.add(school_class)
    await db.commit()
    await db.refresh(school_class)
    return school_class


@pytest.fixture
async def student(db: AsyncSession, school: School) -> Student:
    """Create a test student."""
    student = Student(
        school_id=school.id,
        first_name="John",
        last_name="Doe",
        phone="+998901234567",
        parent_first_name="Michael",
        parent_last_name="Doe",
        parent_phone_1="+998907654321",
        parent_phone_2="+998901111111",
        monthly_fee=Decimal("500000.00"),
        payment_day=5,
        enrolled_at=date(2026, 1, 1),
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


class TestListStudents:
    """Tests for listing students."""

    async def test_owner_can_list_all_students(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test owner can see all students."""
        # Create students
        student1 = Student(
            school_id=school.id,
            first_name="Alice",
            last_name="Smith",
            parent_first_name="Parent",
            parent_last_name="Smith",
            parent_phone_1="+998901111111",
            monthly_fee=Decimal("500000"),
            enrolled_at=date(2026, 1, 1),
        )
        student2 = Student(
            school_id=school.id,
            first_name="Bob",
            last_name="Jones",
            parent_first_name="Parent",
            parent_last_name="Jones",
            parent_phone_1="+998902222222",
            monthly_fee=Decimal("600000"),
            enrolled_at=date(2026, 1, 1),
        )
        db.add_all([student1, student2])
        await db.commit()

        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_students_search(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test searching students by name."""
        student1 = Student(
            school_id=school.id,
            first_name="Alice",
            last_name="Smith",
            parent_first_name="Parent",
            parent_last_name="Smith",
            parent_phone_1="+998901111111",
            monthly_fee=Decimal("500000"),
            enrolled_at=date(2026, 1, 1),
        )
        student2 = Student(
            school_id=school.id,
            first_name="Bob",
            last_name="Jones",
            parent_first_name="Parent",
            parent_last_name="Jones",
            parent_phone_1="+998902222222",
            monthly_fee=Decimal("600000"),
            enrolled_at=date(2026, 1, 1),
        )
        db.add_all([student1, student2])
        await db.commit()

        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"search": "Alice"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["first_name"] == "Alice"

    async def test_list_students_by_school(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test filtering students by school."""
        school1 = School(name="School One")
        school2 = School(name="School Two")
        db.add_all([school1, school2])
        await db.commit()
        await db.refresh(school1)
        await db.refresh(school2)

        student1 = Student(
            school_id=school1.id,
            first_name="Alice",
            last_name="Smith",
            parent_first_name="Parent",
            parent_last_name="Smith",
            parent_phone_1="+998901111111",
            monthly_fee=Decimal("500000"),
            enrolled_at=date(2026, 1, 1),
        )
        student2 = Student(
            school_id=school2.id,
            first_name="Bob",
            last_name="Jones",
            parent_first_name="Parent",
            parent_last_name="Jones",
            parent_phone_1="+998902222222",
            monthly_fee=Decimal("600000"),
            enrolled_at=date(2026, 1, 1),
        )
        db.add_all([student1, student2])
        await db.commit()

        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"school_id": str(school1.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["first_name"] == "Alice"

    async def test_list_students_by_class(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test filtering students by class."""
        class1 = SchoolClass(school_id=school.id, grade=1, section="A")
        class2 = SchoolClass(school_id=school.id, grade=2, section="A")
        db.add_all([class1, class2])
        await db.commit()
        await db.refresh(class1)
        await db.refresh(class2)

        student1 = Student(
            school_id=school.id,
            school_class_id=class1.id,
            first_name="Alice",
            last_name="Smith",
            parent_first_name="Parent",
            parent_last_name="Smith",
            parent_phone_1="+998901111111",
            monthly_fee=Decimal("500000"),
            enrolled_at=date(2026, 1, 1),
        )
        student2 = Student(
            school_id=school.id,
            school_class_id=class2.id,
            first_name="Bob",
            last_name="Jones",
            parent_first_name="Parent",
            parent_last_name="Jones",
            parent_phone_1="+998902222222",
            monthly_fee=Decimal("600000"),
            enrolled_at=date(2026, 1, 1),
        )
        db.add_all([student1, student2])
        await db.commit()

        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"school_class_id": str(class1.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["first_name"] == "Alice"

    async def test_list_students_filter_graduated(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test filtering students by graduation status."""
        student1 = Student(
            school_id=school.id,
            first_name="Alice",
            last_name="Active",
            parent_first_name="Parent",
            parent_last_name="Active",
            parent_phone_1="+998901111111",
            monthly_fee=Decimal("500000"),
            enrolled_at=date(2020, 9, 1),
            graduated_at=None,
        )
        student2 = Student(
            school_id=school.id,
            first_name="Bob",
            last_name="Graduated",
            parent_first_name="Parent",
            parent_last_name="Graduated",
            parent_phone_1="+998902222222",
            monthly_fee=Decimal("500000"),
            enrolled_at=date(2015, 9, 1),
            graduated_at=date(2026, 6, 15),
            is_active=False,
        )
        db.add_all([student1, student2])
        await db.commit()

        # Get only graduated students
        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"graduated": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["first_name"] == "Bob"
        assert data["items"][0]["graduated_at"] == "2026-06-15"

        # Get only non-graduated students
        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"graduated": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["first_name"] == "Alice"


class TestCreateStudent:
    """Tests for creating students."""

    async def test_owner_can_create_student(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test owner can create a student."""
        response = await client.post(
            "/api/v1/students",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "first_name": "New",
                "last_name": "Student",
                "phone": "+998901234567",
                "parent_first_name": "Parent",
                "parent_last_name": "Name",
                "parent_phone_1": "+998907654321",
                "monthly_fee": "500000.00",
                "payment_day": 10,
                "enrolled_at": "2026-01-15",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "New"
        assert data["last_name"] == "Student"
        assert data["parent_first_name"] == "Parent"
        assert data["parent_last_name"] == "Name"
        assert data["parent_phone_1"] == "+998907654321"
        assert data["monthly_fee"] == "500000.00"
        assert data["payment_day"] == 10
        assert data["is_active"] is True
        assert data["school_class_id"] is None
        assert data["graduated_at"] is None

    async def test_create_student_with_class(
        self, client: AsyncClient, owner_token: str, school: School, school_class: SchoolClass
    ):
        """Test creating a student assigned to a class."""
        response = await client.post(
            "/api/v1/students",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "school_class_id": str(school_class.id),
                "first_name": "New",
                "last_name": "Student",
                "parent_first_name": "Parent",
                "parent_last_name": "Name",
                "parent_phone_1": "+998907654321",
                "monthly_fee": "500000.00",
                "enrolled_at": "2026-01-15",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["school_class_id"] == str(school_class.id)

    async def test_create_student_validation(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test student creation validation."""
        # Missing required parent_phone_1
        response = await client.post(
            "/api/v1/students",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "first_name": "Test",
                "last_name": "Student",
                "parent_first_name": "Parent",
                "parent_last_name": "Name",
                "monthly_fee": "500000.00",
                "enrolled_at": "2026-01-15",
            },
        )

        assert response.status_code == 422

    async def test_create_student_invalid_school(
        self, client: AsyncClient, owner_token: str
    ):
        """Test creating student with non-existent school."""
        response = await client.post(
            "/api/v1/students",
            headers=auth_header(owner_token),
            json={
                "school_id": str(uuid4()),
                "first_name": "Test",
                "last_name": "Student",
                "parent_first_name": "Parent",
                "parent_last_name": "Name",
                "parent_phone_1": "+998901234567",
                "monthly_fee": "500000.00",
                "enrolled_at": "2026-01-15",
            },
        )

        assert response.status_code == 404

    async def test_create_student_invalid_payment_day(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test payment day must be between 1 and 28."""
        response = await client.post(
            "/api/v1/students",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "first_name": "Test",
                "last_name": "Student",
                "parent_first_name": "Parent",
                "parent_last_name": "Name",
                "parent_phone_1": "+998901234567",
                "monthly_fee": "500000.00",
                "payment_day": 31,  # Invalid
                "enrolled_at": "2026-01-15",
            },
        )

        assert response.status_code == 422


class TestGetStudent:
    """Tests for getting a single student."""

    async def test_get_student_success(
        self, client: AsyncClient, owner_token: str, student: Student
    ):
        """Test getting a student by ID."""
        response = await client.get(
            f"/api/v1/students/{student.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"

    async def test_get_student_not_found(
        self, client: AsyncClient, owner_token: str
    ):
        """Test getting non-existent student."""
        response = await client.get(
            f"/api/v1/students/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestUpdateStudent:
    """Tests for updating students."""

    async def test_update_student_success(
        self, client: AsyncClient, owner_token: str, student: Student
    ):
        """Test updating a student."""
        response = await client.patch(
            f"/api/v1/students/{student.id}",
            headers=auth_header(owner_token),
            json={"first_name": "Jane", "monthly_fee": "600000.00"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["monthly_fee"] == "600000.00"
        assert data["last_name"] == "Doe"  # Unchanged

    async def test_update_student_partial(
        self, client: AsyncClient, owner_token: str, student: Student
    ):
        """Test partial update only changes specified fields."""
        original_fee = student.monthly_fee

        response = await client.patch(
            f"/api/v1/students/{student.id}",
            headers=auth_header(owner_token),
            json={"first_name": "Updated"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert Decimal(data["monthly_fee"]) == original_fee

    async def test_update_student_class(
        self, client: AsyncClient, owner_token: str, student: Student, school_class: SchoolClass
    ):
        """Test assigning a student to a class."""
        response = await client.patch(
            f"/api/v1/students/{student.id}",
            headers=auth_header(owner_token),
            json={"school_class_id": str(school_class.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["school_class_id"] == str(school_class.id)

    async def test_update_student_graduated(
        self, client: AsyncClient, owner_token: str, student: Student
    ):
        """Test graduating a student."""
        response = await client.patch(
            f"/api/v1/students/{student.id}",
            headers=auth_header(owner_token),
            json={"graduated_at": "2026-06-15", "is_active": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["graduated_at"] == "2026-06-15"
        assert data["is_active"] is False


class TestSQLInjection:
    """Tests for SQL injection protection."""

    async def test_search_sql_injection_single_quote(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test search is protected against single quote injection."""
        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"search": "'; DROP TABLE students; --"},
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_search_sql_injection_or_true(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test search is protected against OR 1=1 injection."""
        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"search": "' OR '1'='1"},
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_search_sql_injection_union(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test search is protected against UNION injection."""
        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"search": "' UNION SELECT * FROM users --"},
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_search_sql_injection_comment(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test search is protected against comment injection."""
        response = await client.get(
            "/api/v1/students",
            headers=auth_header(owner_token),
            params={"search": "test'--"},
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_create_student_sql_injection_in_name(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test create is protected against SQL injection in name field."""
        response = await client.post(
            "/api/v1/students",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "first_name": "'; DROP TABLE students; --",
                "last_name": "Test",
                "parent_first_name": "Parent",
                "parent_last_name": "Name",
                "parent_phone_1": "+998901234567",
                "monthly_fee": "500000.00",
                "enrolled_at": "2026-01-15",
            },
        )

        # Should succeed - the malicious string is just stored as data
        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "'; DROP TABLE students; --"


class TestDeleteStudent:
    """Tests for deleting students."""

    async def test_delete_student_success(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, student: Student
    ):
        """Test soft deleting a student."""
        response = await client.delete(
            f"/api/v1/students/{student.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 204

        # Verify it's deactivated
        await db.refresh(student)
        assert student.is_active is False

    async def test_delete_student_not_found(
        self, client: AsyncClient, owner_token: str
    ):
        """Test deleting non-existent student."""
        response = await client.delete(
            f"/api/v1/students/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
