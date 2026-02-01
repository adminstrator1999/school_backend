"""Tests for school classes API."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Employee
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
async def teacher(db: AsyncSession, school: School) -> Employee:
    """Create a test teacher/employee."""
    teacher = Employee(
        school_id=school.id,
        first_name="John",
        last_name="Teacher",
        position="Teacher",
        salary=Decimal("5000000.00"),
    )
    db.add(teacher)
    await db.commit()
    await db.refresh(teacher)
    return teacher


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


class TestListClasses:
    """Tests for listing school classes."""

    async def test_list_classes_empty(
        self, client: AsyncClient, owner_token: str
    ):
        """Test listing classes when none exist."""
        response = await client.get(
            "/api/v1/classes",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_all_classes(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test listing all classes."""
        # Create classes
        class1 = SchoolClass(school_id=school.id, grade=1, section="A")
        class2 = SchoolClass(school_id=school.id, grade=1, section="B")
        class3 = SchoolClass(school_id=school.id, grade=2, section="A")
        db.add_all([class1, class2, class3])
        await db.commit()

        response = await client.get(
            "/api/v1/classes",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        # Should be ordered by grade, then section
        assert data["items"][0]["grade"] == 1
        assert data["items"][0]["section"] == "A"
        assert data["items"][1]["grade"] == 1
        assert data["items"][1]["section"] == "B"
        assert data["items"][2]["grade"] == 2

    async def test_list_classes_filter_by_school(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test filtering classes by school."""
        school1 = School(name="School One")
        school2 = School(name="School Two")
        db.add_all([school1, school2])
        await db.commit()
        await db.refresh(school1)
        await db.refresh(school2)

        class1 = SchoolClass(school_id=school1.id, grade=1, section="A")
        class2 = SchoolClass(school_id=school2.id, grade=1, section="A")
        db.add_all([class1, class2])
        await db.commit()

        response = await client.get(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            params={"school_id": str(school1.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["school_id"] == str(school1.id)

    async def test_list_classes_filter_by_grade(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test filtering classes by grade."""
        class1 = SchoolClass(school_id=school.id, grade=1, section="A")
        class2 = SchoolClass(school_id=school.id, grade=2, section="A")
        db.add_all([class1, class2])
        await db.commit()

        response = await client.get(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            params={"grade": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["grade"] == 1


class TestCreateClass:
    """Tests for creating school classes."""

    async def test_owner_can_create_class(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test owner can create a class."""
        response = await client.post(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "grade": 5,
                "section": "b",  # Should be normalized to uppercase
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["grade"] == 5
        assert data["section"] == "B"  # Uppercased
        assert data["name"] == "5th B"
        assert data["is_active"] is True
        assert data["homeroom_teacher_id"] is None

    async def test_create_class_with_homeroom_teacher(
        self, client: AsyncClient, owner_token: str, school: School, teacher: Employee
    ):
        """Test creating a class with a homeroom teacher assigned."""
        response = await client.post(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "grade": 3,
                "section": "A",
                "homeroom_teacher_id": str(teacher.id),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["grade"] == 3
        assert data["homeroom_teacher_id"] == str(teacher.id)

    async def test_create_class_name_formatting(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test class name formatting (1st, 2nd, 3rd, 4th, etc.)."""
        grades_and_names = [
            (1, "A", "1st A"),
            (2, "A", "2nd A"),
            (3, "A", "3rd A"),
            (4, "A", "4th A"),
            (11, "B", "11th B"),
        ]

        for grade, section, expected_name in grades_and_names:
            response = await client.post(
                "/api/v1/classes",
                headers=auth_header(owner_token),
                json={
                    "school_id": str(school.id),
                    "grade": grade,
                    "section": section,
                },
            )
            assert response.status_code == 201
            assert response.json()["name"] == expected_name

    async def test_create_class_validation_grade(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test grade must be between 1 and 11."""
        # Grade 0
        response = await client.post(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            json={"school_id": str(school.id), "grade": 0, "section": "A"},
        )
        assert response.status_code == 422

        # Grade 12
        response = await client.post(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            json={"school_id": str(school.id), "grade": 12, "section": "A"},
        )
        assert response.status_code == 422

    async def test_create_class_invalid_school(
        self, client: AsyncClient, owner_token: str
    ):
        """Test creating class with non-existent school."""
        response = await client.post(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            json={"school_id": str(uuid4()), "grade": 1, "section": "A"},
        )

        assert response.status_code == 404
        assert "School not found" in response.json()["detail"]

    async def test_create_class_duplicate(
        self, client: AsyncClient, owner_token: str, school_class: SchoolClass
    ):
        """Test cannot create duplicate grade/section for same school."""
        response = await client.post(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school_class.school_id),
                "grade": school_class.grade,
                "section": school_class.section,
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


class TestGetClass:
    """Tests for getting a single class."""

    async def test_get_class_success(
        self, client: AsyncClient, owner_token: str, school_class: SchoolClass
    ):
        """Test getting a class by ID."""
        response = await client.get(
            f"/api/v1/classes/{school_class.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(school_class.id)
        assert data["grade"] == 1
        assert data["section"] == "A"
        assert data["name"] == "1st A"

    async def test_get_class_not_found(
        self, client: AsyncClient, owner_token: str
    ):
        """Test getting non-existent class."""
        response = await client.get(
            f"/api/v1/classes/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestUpdateClass:
    """Tests for updating school classes."""

    async def test_update_class_success(
        self, client: AsyncClient, owner_token: str, school_class: SchoolClass
    ):
        """Test updating a class."""
        response = await client.patch(
            f"/api/v1/classes/{school_class.id}",
            headers=auth_header(owner_token),
            json={"section": "c"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["section"] == "C"  # Uppercased
        assert data["name"] == "1st C"

    async def test_update_class_homeroom_teacher(
        self, client: AsyncClient, owner_token: str, school_class: SchoolClass, teacher: Employee
    ):
        """Test assigning a homeroom teacher to a class."""
        # Initially no teacher
        assert school_class.homeroom_teacher_id is None

        response = await client.patch(
            f"/api/v1/classes/{school_class.id}",
            headers=auth_header(owner_token),
            json={"homeroom_teacher_id": str(teacher.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["homeroom_teacher_id"] == str(teacher.id)

    async def test_update_class_grade(
        self, client: AsyncClient, owner_token: str, school_class: SchoolClass
    ):
        """Test updating class grade."""
        response = await client.patch(
            f"/api/v1/classes/{school_class.id}",
            headers=auth_header(owner_token),
            json={"grade": 5},
        )

        assert response.status_code == 200
        assert response.json()["grade"] == 5
        assert response.json()["name"] == "5th A"

    async def test_update_class_duplicate_check(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test cannot update to duplicate grade/section."""
        class1 = SchoolClass(school_id=school.id, grade=1, section="A")
        class2 = SchoolClass(school_id=school.id, grade=2, section="A")
        db.add_all([class1, class2])
        await db.commit()
        await db.refresh(class1)
        await db.refresh(class2)

        # Try to change class2 to grade 1, section A (already exists)
        response = await client.patch(
            f"/api/v1/classes/{class2.id}",
            headers=auth_header(owner_token),
            json={"grade": 1},
        )

        assert response.status_code == 409


class TestDeleteClass:
    """Tests for deleting school classes."""

    async def test_delete_class_success(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school_class: SchoolClass
    ):
        """Test soft deleting a class."""
        response = await client.delete(
            f"/api/v1/classes/{school_class.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 204

        # Verify it's deactivated
        await db.refresh(school_class)
        assert school_class.is_active is False

    async def test_delete_class_not_found(
        self, client: AsyncClient, owner_token: str
    ):
        """Test deleting non-existent class."""
        response = await client.delete(
            f"/api/v1/classes/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestPromoteStudents:
    """Tests for promoting students to next grade."""

    async def test_promote_students_success(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test promoting students to next grade."""
        # Create classes for grades 1-3
        class1a = SchoolClass(school_id=school.id, grade=1, section="A")
        class2a = SchoolClass(school_id=school.id, grade=2, section="A")
        class3a = SchoolClass(school_id=school.id, grade=3, section="A")
        db.add_all([class1a, class2a, class3a])
        await db.commit()
        await db.refresh(class1a)
        await db.refresh(class2a)

        # Create students in grade 1
        student1 = Student(
            school_id=school.id,
            school_class_id=class1a.id,
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
            school_class_id=class1a.id,
            first_name="Bob",
            last_name="Jones",
            parent_first_name="Parent",
            parent_last_name="Jones",
            parent_phone_1="+998902222222",
            monthly_fee=Decimal("500000"),
            enrolled_at=date(2026, 1, 1),
        )
        db.add_all([student1, student2])
        await db.commit()

        response = await client.post(
            f"/api/v1/classes/promote/{school.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["promoted"] == 2
        assert data["graduated"] == 0

        # Verify students are now in grade 2
        await db.refresh(student1)
        await db.refresh(student2)
        assert student1.school_class_id == class2a.id
        assert student2.school_class_id == class2a.id

    async def test_promote_graduates_grade_11(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test students in grade 11 get graduated."""
        # Create class for grade 11
        class11 = SchoolClass(school_id=school.id, grade=11, section="A")
        db.add(class11)
        await db.commit()
        await db.refresh(class11)

        # Create student in grade 11
        student = Student(
            school_id=school.id,
            school_class_id=class11.id,
            first_name="Graduate",
            last_name="Student",
            parent_first_name="Parent",
            parent_last_name="Name",
            parent_phone_1="+998903333333",
            monthly_fee=Decimal("500000"),
            enrolled_at=date(2015, 9, 1),
        )
        db.add(student)
        await db.commit()

        response = await client.post(
            f"/api/v1/classes/promote/{school.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["graduated"] == 1

        # Verify student is graduated and deactivated
        await db.refresh(student)
        assert student.graduated_at is not None
        assert student.is_active is False

    async def test_promote_invalid_school(
        self, client: AsyncClient, owner_token: str
    ):
        """Test promoting with non-existent school."""
        response = await client.post(
            f"/api/v1/classes/promote/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestSQLInjection:
    """Tests for SQL injection protection in classes."""

    async def test_create_class_sql_injection_section(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test create is protected against SQL injection in section."""
        response = await client.post(
            "/api/v1/classes",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "grade": 1,
                "section": "'; DROP",
            },
        )

        # Should succeed - the malicious string is just stored as data
        assert response.status_code == 201
        data = response.json()
        assert data["section"] == "'; DROP".upper()
