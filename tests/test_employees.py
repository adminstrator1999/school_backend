"""Tests for employees API."""

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Employee, Position
from app.models.school import School
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
async def position(db: AsyncSession, school: School) -> Position:
    """Create a test position."""
    position = Position(
        name="Math Teacher",
        school_id=school.id,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return position


@pytest.fixture
async def system_position(db: AsyncSession) -> Position:
    """Create a system-wide position."""
    position = Position(
        name="Director",
        is_system=True,
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
        last_name="Teacher",
        phone="+998901234567",
        salary=Decimal("5000000.00"),
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


class TestListEmployees:
    """Tests for listing employees."""

    async def test_list_employees_empty(
        self, client: AsyncClient, owner_token: str
    ):
        """Test listing employees when none exist."""
        response = await client.get(
            "/api/v1/employees",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_owner_can_list_all_employees(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School, position: Position
    ):
        """Test owner can see all employees."""
        employee1 = Employee(
            school_id=school.id,
            position_id=position.id,
            first_name="Alice",
            last_name="Teacher",
            salary=Decimal("4500000"),
        )
        employee2 = Employee(
            school_id=school.id,
            position_id=position.id,
            first_name="Bob",
            last_name="Admin",
            salary=Decimal("3500000"),
        )
        db.add_all([employee1, employee2])
        await db.commit()

        response = await client.get(
            "/api/v1/employees",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_employees_search(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School, position: Position
    ):
        """Test searching employees by name."""
        employee1 = Employee(
            school_id=school.id,
            position_id=position.id,
            first_name="Alice",
            last_name="Smith",
            salary=Decimal("4500000"),
        )
        employee2 = Employee(
            school_id=school.id,
            position_id=position.id,
            first_name="Bob",
            last_name="Jones",
            salary=Decimal("4500000"),
        )
        db.add_all([employee1, employee2])
        await db.commit()

        response = await client.get(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            params={"search": "Alice"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["first_name"] == "Alice"

    async def test_list_employees_filter_by_position(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test filtering employees by position ID."""
        position1 = Position(name="Teacher", school_id=school.id)
        position2 = Position(name="Administrator", school_id=school.id)
        db.add_all([position1, position2])
        await db.commit()
        await db.refresh(position1)
        await db.refresh(position2)

        employee1 = Employee(
            school_id=school.id,
            position_id=position1.id,
            first_name="Alice",
            last_name="Smith",
            salary=Decimal("4500000"),
        )
        employee2 = Employee(
            school_id=school.id,
            position_id=position2.id,
            first_name="Bob",
            last_name="Jones",
            salary=Decimal("3500000"),
        )
        db.add_all([employee1, employee2])
        await db.commit()

        response = await client.get(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            params={"position_id": str(position1.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["first_name"] == "Alice"
        assert data["items"][0]["position"]["name"] == "Teacher"

    async def test_list_employees_filter_by_school(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test filtering employees by school."""
        school1 = School(name="School One")
        school2 = School(name="School Two")
        db.add_all([school1, school2])
        await db.commit()
        await db.refresh(school1)
        await db.refresh(school2)

        position1 = Position(name="Teacher", school_id=school1.id)
        position2 = Position(name="Teacher", school_id=school2.id)
        db.add_all([position1, position2])
        await db.commit()
        await db.refresh(position1)
        await db.refresh(position2)

        employee1 = Employee(
            school_id=school1.id,
            position_id=position1.id,
            first_name="Alice",
            last_name="Smith",
            salary=Decimal("4500000"),
        )
        employee2 = Employee(
            school_id=school2.id,
            position_id=position2.id,
            first_name="Bob",
            last_name="Jones",
            salary=Decimal("4500000"),
        )
        db.add_all([employee1, employee2])
        await db.commit()

        response = await client.get(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            params={"school_id": str(school1.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["first_name"] == "Alice"


class TestCreateEmployee:
    """Tests for creating employees."""

    async def test_owner_can_create_employee(
        self, client: AsyncClient, owner_token: str, school: School, position: Position
    ):
        """Test owner can create an employee."""
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "position_id": str(position.id),
                "first_name": "New",
                "last_name": "Employee",
                "phone": "+998901234567",
                "salary": "4500000.00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "New"
        assert data["last_name"] == "Employee"
        assert data["full_name"] == "New Employee"
        assert data["position"]["name"] == "Math Teacher"
        assert data["position_id"] == str(position.id)
        assert data["salary"] == "4500000.00"
        assert data["is_active"] is True
        assert data["profile_picture"] is None

    async def test_create_employee_with_system_position(
        self, client: AsyncClient, owner_token: str, school: School, system_position: Position
    ):
        """Test creating employee with a system-wide position."""
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "position_id": str(system_position.id),
                "first_name": "School",
                "last_name": "Director",
                "salary": "10000000.00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["position"]["name"] == "Director"

    async def test_create_employee_with_profile_picture(
        self, client: AsyncClient, owner_token: str, school: School, position: Position
    ):
        """Test creating employee with profile picture."""
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "position_id": str(position.id),
                "first_name": "Jane",
                "last_name": "Teacher",
                "salary": "4000000.00",
                "profile_picture": "https://example.com/photo.jpg",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["profile_picture"] == "https://example.com/photo.jpg"

    async def test_create_employee_validation(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test employee creation validation - missing position_id."""
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "first_name": "Test",
                "last_name": "Employee",
                "salary": "4500000.00",
            },
        )

        assert response.status_code == 422

    async def test_create_employee_invalid_school(
        self, client: AsyncClient, owner_token: str, position: Position
    ):
        """Test creating employee with non-existent school."""
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(uuid4()),
                "position_id": str(position.id),
                "first_name": "Test",
                "last_name": "Employee",
                "salary": "4500000.00",
            },
        )

        assert response.status_code == 404
        assert "School not found" in response.json()["detail"]

    async def test_create_employee_invalid_position(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test creating employee with non-existent position."""
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "position_id": str(uuid4()),
                "first_name": "Test",
                "last_name": "Employee",
                "salary": "4500000.00",
            },
        )

        assert response.status_code == 404
        assert "Position not found" in response.json()["detail"]

    async def test_create_employee_position_from_other_school(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, school: School
    ):
        """Test creating employee with position from different school."""
        # Create another school with its own position
        other_school = School(name="Other School")
        db.add(other_school)
        await db.commit()
        await db.refresh(other_school)

        other_position = Position(name="Other Position", school_id=other_school.id)
        db.add(other_position)
        await db.commit()
        await db.refresh(other_position)

        # Try to use other school's position
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "position_id": str(other_position.id),
                "first_name": "Test",
                "last_name": "Employee",
                "salary": "4500000.00",
            },
        )

        assert response.status_code == 400
        assert "Position does not belong to this school" in response.json()["detail"]

    async def test_create_employee_invalid_salary(
        self, client: AsyncClient, owner_token: str, school: School, position: Position
    ):
        """Test salary must be positive."""
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "position_id": str(position.id),
                "first_name": "Test",
                "last_name": "Employee",
                "salary": "-100.00",
            },
        )

        assert response.status_code == 422


class TestGetEmployee:
    """Tests for getting a single employee."""

    async def test_get_employee_success(
        self, client: AsyncClient, owner_token: str, employee: Employee
    ):
        """Test getting an employee by ID."""
        response = await client.get(
            f"/api/v1/employees/{employee.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "John"
        assert data["last_name"] == "Teacher"
        assert data["full_name"] == "John Teacher"
        assert data["position"]["name"] == "Math Teacher"

    async def test_get_employee_not_found(
        self, client: AsyncClient, owner_token: str
    ):
        """Test getting non-existent employee."""
        response = await client.get(
            f"/api/v1/employees/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestUpdateEmployee:
    """Tests for updating employees."""

    async def test_update_employee_success(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, employee: Employee, school: School
    ):
        """Test updating an employee's position and salary."""
        new_position = Position(name="Senior Teacher", school_id=school.id)
        db.add(new_position)
        await db.commit()
        await db.refresh(new_position)

        response = await client.patch(
            f"/api/v1/employees/{employee.id}",
            headers=auth_header(owner_token),
            json={"position_id": str(new_position.id), "salary": "6000000.00"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["position"]["name"] == "Senior Teacher"
        assert data["salary"] == "6000000.00"
        assert data["first_name"] == "John"  # Unchanged

    async def test_update_employee_partial(
        self, client: AsyncClient, owner_token: str, employee: Employee
    ):
        """Test partial update only changes specified fields."""
        original_salary = employee.salary

        response = await client.patch(
            f"/api/v1/employees/{employee.id}",
            headers=auth_header(owner_token),
            json={"first_name": "Updated"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert Decimal(data["salary"]) == original_salary

    async def test_update_employee_profile_picture(
        self, client: AsyncClient, owner_token: str, employee: Employee
    ):
        """Test updating employee profile picture."""
        response = await client.patch(
            f"/api/v1/employees/{employee.id}",
            headers=auth_header(owner_token),
            json={"profile_picture": "https://example.com/new-photo.jpg"},
        )

        assert response.status_code == 200
        assert response.json()["profile_picture"] == "https://example.com/new-photo.jpg"

    async def test_update_employee_position_from_other_school(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, employee: Employee
    ):
        """Test updating employee with position from different school."""
        # Create another school with its own position
        other_school = School(name="Other School")
        db.add(other_school)
        await db.commit()
        await db.refresh(other_school)

        other_position = Position(name="Other Position", school_id=other_school.id)
        db.add(other_position)
        await db.commit()
        await db.refresh(other_position)

        response = await client.patch(
            f"/api/v1/employees/{employee.id}",
            headers=auth_header(owner_token),
            json={"position_id": str(other_position.id)},
        )

        assert response.status_code == 400
        assert "Position does not belong to this school" in response.json()["detail"]


class TestDeleteEmployee:
    """Tests for deleting employees."""

    async def test_delete_employee_success(
        self, client: AsyncClient, db: AsyncSession, owner_token: str, employee: Employee
    ):
        """Test soft deleting an employee."""
        response = await client.delete(
            f"/api/v1/employees/{employee.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 204

        # Verify it's deactivated
        await db.refresh(employee)
        assert employee.is_active is False

    async def test_delete_employee_not_found(
        self, client: AsyncClient, owner_token: str
    ):
        """Test deleting non-existent employee."""
        response = await client.delete(
            f"/api/v1/employees/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestSQLInjection:
    """Tests for SQL injection protection."""

    async def test_search_sql_injection(
        self, client: AsyncClient, owner_token: str, school: School
    ):
        """Test search is protected against SQL injection."""
        response = await client.get(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            params={"search": "'; DROP TABLE employees; --"},
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_create_employee_sql_injection_in_name(
        self, client: AsyncClient, owner_token: str, school: School, position: Position
    ):
        """Test create is protected against SQL injection in name field."""
        response = await client.post(
            "/api/v1/employees",
            headers=auth_header(owner_token),
            json={
                "school_id": str(school.id),
                "position_id": str(position.id),
                "first_name": "'; DROP TABLE employees; --",
                "last_name": "Test",
                "salary": "4500000.00",
            },
        )

        # Should succeed - the malicious string is just stored as data
        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "'; DROP TABLE employees; --"
