"""Tests for schools API."""

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from tests.conftest import auth_header


class TestListSchools:
    """Tests for listing schools."""

    async def test_owner_can_list_all_schools(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test owner can see all schools."""
        # Create some schools
        school1 = School(name="School One", address="Address 1")
        school2 = School(name="School Two", address="Address 2")
        db.add_all([school1, school2])
        await db.commit()

        response = await client.get(
            "/api/v1/schools",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_schools_search(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test searching schools by name."""
        school1 = School(name="Alpha Academy")
        school2 = School(name="Beta School")
        db.add_all([school1, school2])
        await db.commit()

        response = await client.get(
            "/api/v1/schools",
            headers=auth_header(owner_token),
            params={"search": "Alpha"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Alpha Academy"

    async def test_list_schools_pagination(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test pagination works correctly."""
        for i in range(5):
            db.add(School(name=f"School {i}"))
        await db.commit()

        response = await client.get(
            "/api/v1/schools",
            headers=auth_header(owner_token),
            params={"skip": 0, "limit": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2


class TestCreateSchool:
    """Tests for creating schools."""

    async def test_owner_can_create_school(
        self, client: AsyncClient, owner_token: str
    ):
        """Test owner can create a school."""
        response = await client.post(
            "/api/v1/schools",
            headers=auth_header(owner_token),
            json={
                "name": "New School",
                "address": "123 Main St",
                "phone": "+998901234567",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New School"
        assert data["address"] == "123 Main St"
        assert data["is_active"] is True

    async def test_superuser_can_create_school(
        self, client: AsyncClient, superuser_token: str
    ):
        """Test superuser can create a school."""
        response = await client.post(
            "/api/v1/schools",
            headers=auth_header(superuser_token),
            json={"name": "Superuser School"},
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Superuser School"

    async def test_create_school_validation(
        self, client: AsyncClient, owner_token: str
    ):
        """Test school creation validation."""
        # Empty name
        response = await client.post(
            "/api/v1/schools",
            headers=auth_header(owner_token),
            json={"name": ""},
        )

        assert response.status_code == 422


class TestGetSchool:
    """Tests for getting a single school."""

    async def test_get_school_success(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test getting a school by ID."""
        school = School(name="Test School")
        db.add(school)
        await db.commit()
        await db.refresh(school)

        response = await client.get(
            f"/api/v1/schools/{school.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Test School"

    async def test_get_school_not_found(
        self, client: AsyncClient, owner_token: str
    ):
        """Test getting non-existent school."""
        response = await client.get(
            f"/api/v1/schools/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404


class TestUpdateSchool:
    """Tests for updating schools."""

    async def test_update_school_success(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test updating a school."""
        school = School(name="Old Name")
        db.add(school)
        await db.commit()
        await db.refresh(school)

        response = await client.patch(
            f"/api/v1/schools/{school.id}",
            headers=auth_header(owner_token),
            json={"name": "New Name", "address": "New Address"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["address"] == "New Address"

    async def test_update_school_partial(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test partial update only changes specified fields."""
        school = School(name="Original", address="Original Address")
        db.add(school)
        await db.commit()
        await db.refresh(school)

        response = await client.patch(
            f"/api/v1/schools/{school.id}",
            headers=auth_header(owner_token),
            json={"name": "Updated"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
        assert data["address"] == "Original Address"  # Unchanged


class TestUpdateSubscription:
    """Tests for updating school subscription."""

    async def test_update_subscription(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test updating subscription dates."""
        school = School(name="Test School")
        db.add(school)
        await db.commit()
        await db.refresh(school)

        response = await client.patch(
            f"/api/v1/schools/{school.id}/subscription",
            headers=auth_header(owner_token),
            json={
                "subscription_starts_at": "2026-01-01T00:00:00Z",
                "subscription_expires_at": "2027-01-01T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["subscription_starts_at"] is not None
        assert data["subscription_expires_at"] is not None


class TestDeleteSchool:
    """Tests for deleting schools."""

    async def test_delete_school_success(
        self, client: AsyncClient, db: AsyncSession, owner_token: str
    ):
        """Test soft deleting a school."""
        school = School(name="To Delete")
        db.add(school)
        await db.commit()
        await db.refresh(school)

        response = await client.delete(
            f"/api/v1/schools/{school.id}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 204

        # Verify it's deactivated
        await db.refresh(school)
        assert school.is_active is False

    async def test_delete_school_not_found(
        self, client: AsyncClient, owner_token: str
    ):
        """Test deleting non-existent school."""
        response = await client.delete(
            f"/api/v1/schools/{uuid4()}",
            headers=auth_header(owner_token),
        )

        assert response.status_code == 404
