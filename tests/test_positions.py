"""Tests for Positions API."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Position
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
async def system_position(db: AsyncSession) -> Position:
    """Create a system-wide position."""
    position = Position(
        name="System Admin",
        is_system=True,
    )
    db.add(position)
    await db.commit()
    await db.refresh(position)
    return position


# ============== Tests ==============


class TestListPositions:
    """Tests for listing positions."""

    async def test_list_positions_empty(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test listing positions when none exist."""
        response = await client.get(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_positions_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        superuser_token: str,
        school: School,
    ):
        """Test listing positions with data."""
        # Create system position
        system_pos = Position(name="System Admin", is_system=True)
        # Create school position
        school_pos = Position(name="Teacher", school_id=school.id)
        db.add_all([system_pos, school_pos])
        await db.commit()

        response = await client.get(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
            params={"school_id": str(school.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # System + school position
        names = [p["name"] for p in data["items"]]
        assert "System Admin" in names
        assert "Teacher" in names

    async def test_list_positions_search(
        self,
        client: AsyncClient,
        db: AsyncSession,
        superuser_token: str,
        school: School,
    ):
        """Test searching positions by name."""
        pos1 = Position(name="Teacher", school_id=school.id)
        pos2 = Position(name="Cleaner", school_id=school.id)
        pos3 = Position(name="Guard", school_id=school.id)
        db.add_all([pos1, pos2, pos3])
        await db.commit()

        response = await client.get(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
            params={"school_id": str(school.id), "search": "teach"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Teacher"


class TestCreatePosition:
    """Tests for creating positions."""

    async def test_create_position_success(
        self,
        client: AsyncClient,
        superuser_token: str,
        school: School,
    ):
        """Test creating a position for a school."""
        response = await client.post(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
            json={
                "name": "Mathematics Teacher",
                "school_id": str(school.id),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Mathematics Teacher"
        assert data["school_id"] == str(school.id)
        assert data["is_system"] is False
        assert data["is_active"] is True

    async def test_create_system_position(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test creating a system-wide position."""
        response = await client.post(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
            json={
                "name": "Director",
                "is_system": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Director"
        assert data["school_id"] is None
        assert data["is_system"] is True

    async def test_create_position_invalid_school(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test creating a position with invalid school ID."""
        response = await client.post(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
            json={
                "name": "Teacher",
                "school_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 404
        assert "School not found" in response.json()["detail"]


class TestGetPosition:
    """Tests for getting a single position."""

    async def test_get_position_success(
        self,
        client: AsyncClient,
        superuser_token: str,
        position: Position,
    ):
        """Test getting a position by ID."""
        response = await client.get(
            f"/api/v1/positions/{position.id}",
            headers=auth_header(superuser_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(position.id)
        assert data["name"] == "Teacher"

    async def test_get_position_not_found(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test getting a non-existent position."""
        response = await client.get(
            f"/api/v1/positions/{uuid.uuid4()}",
            headers=auth_header(superuser_token),
        )

        assert response.status_code == 404


class TestUpdatePosition:
    """Tests for updating positions."""

    async def test_update_position_success(
        self,
        client: AsyncClient,
        superuser_token: str,
        position: Position,
    ):
        """Test updating a position."""
        response = await client.patch(
            f"/api/v1/positions/{position.id}",
            headers=auth_header(superuser_token),
            json={"name": "Senior Teacher"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Senior Teacher"

    async def test_update_position_not_found(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test updating a non-existent position."""
        response = await client.patch(
            f"/api/v1/positions/{uuid.uuid4()}",
            headers=auth_header(superuser_token),
            json={"name": "Updated"},
        )

        assert response.status_code == 404


class TestDeletePosition:
    """Tests for deleting positions."""

    async def test_delete_position_success(
        self,
        client: AsyncClient,
        superuser_token: str,
        school: School,
        position: Position,
    ):
        """Test deleting a position (soft delete)."""
        response = await client.delete(
            f"/api/v1/positions/{position.id}",
            headers=auth_header(superuser_token),
        )

        assert response.status_code == 204

        # Position should be soft deleted (not visible)
        get_response = await client.get(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
            params={"school_id": str(school.id)},
        )
        assert get_response.status_code == 200
        assert get_response.json()["total"] == 0

    async def test_delete_position_not_found(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test deleting a non-existent position."""
        response = await client.delete(
            f"/api/v1/positions/{uuid.uuid4()}",
            headers=auth_header(superuser_token),
        )

        assert response.status_code == 404

    async def test_delete_system_position_forbidden(
        self,
        client: AsyncClient,
        superuser_token: str,
        system_position: Position,
    ):
        """Test that system positions cannot be deleted."""
        response = await client.delete(
            f"/api/v1/positions/{system_position.id}",
            headers=auth_header(superuser_token),
        )

        assert response.status_code == 403
        assert "system positions" in response.json()["detail"].lower()


class TestSQLInjection:
    """Tests for SQL injection protection."""

    async def test_position_search_sql_injection(
        self,
        client: AsyncClient,
        superuser_token: str,
    ):
        """Test that search parameter is safe from SQL injection."""
        malicious_search = "'; DROP TABLE positions; --"

        response = await client.get(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
            params={"search": malicious_search},
        )

        assert response.status_code == 200

    async def test_position_create_sql_injection(
        self,
        client: AsyncClient,
        superuser_token: str,
        school: School,
    ):
        """Test that name field is safe from SQL injection."""
        response = await client.post(
            "/api/v1/positions",
            headers=auth_header(superuser_token),
            json={
                "name": "'; DROP TABLE positions; --",
                "school_id": str(school.id),
            },
        )

        assert response.status_code == 201
        assert response.json()["name"] == "'; DROP TABLE positions; --"
