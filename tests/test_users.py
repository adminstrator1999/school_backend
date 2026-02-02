"""Tests for user endpoints."""

import uuid

from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import get_password_hash
from app.models.user import User
from tests.conftest import auth_header


class TestGetMe:
    """Tests for GET /users/me endpoint."""

    async def test_get_me_success(self, client: AsyncClient, owner_token, owner_user):
        """Test getting own profile."""
        response = await client.get(
            "/api/v1/users/me",
            headers=auth_header(owner_token),
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+998901111111"
        assert data["first_name"] == "Owner"
        assert data["role"] == "owner"

    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Test getting profile without auth."""
        response = await client.get("/api/v1/users/me")
        
        assert response.status_code == 401


class TestUpdateMe:
    """Tests for PATCH /users/me endpoint."""

    async def test_update_me_success(self, client: AsyncClient, owner_token):
        """Test updating own profile."""
        response = await client.patch(
            "/api/v1/users/me",
            headers=auth_header(owner_token),
            json={"first_name": "Updated"},
        )
        
        assert response.status_code == 200
        assert response.json()["first_name"] == "Updated"

    async def test_update_me_phone(self, client: AsyncClient, superuser_token):
        """Test updating own phone number."""
        response = await client.patch(
            "/api/v1/users/me",
            headers=auth_header(superuser_token),
            json={"phone_number": "+998903333333"},
        )
        
        assert response.status_code == 200
        assert response.json()["phone_number"] == "+998903333333"


class TestChangePassword:
    """Tests for POST /users/me/password endpoint."""

    async def test_change_password_success(
        self, client: AsyncClient, db: AsyncSession, owner_user, owner_token
    ):
        """Test changing password."""
        response = await client.post(
            "/api/v1/users/me/password",
            headers=auth_header(owner_token),
            json={
                "current_password": "password123",
                "new_password": "newpassword123",
            },
        )
        
        assert response.status_code == 204
        
        # Verify can login with new password
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "+998901111111", "password": "newpassword123"},
        )
        assert login_response.status_code == 200

    async def test_change_password_wrong_current(
        self, client: AsyncClient, owner_token
    ):
        """Test changing password with wrong current password."""
        response = await client.post(
            "/api/v1/users/me/password",
            headers=auth_header(owner_token),
            json={
                "current_password": "wrongpassword",
                "new_password": "newpassword123",
            },
        )
        
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]


class TestCreateUser:
    """Tests for POST /users endpoint."""

    async def test_owner_can_create_superuser(
        self, client: AsyncClient, db: AsyncSession, owner_token
    ):
        """Test that owner can create superuser."""
        response = await client.post(
            "/api/v1/users",
            headers=auth_header(owner_token),
            json={
                "phone_number": "+998904444444",
                "password": "password123",
                "first_name": "New",
                "last_name": "Superuser",
                "role": "superuser",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "superuser"
        
        # Cleanup
        await db.execute(delete(User).where(User.phone_number == "+998904444444"))
        await db.commit()

    async def test_superuser_cannot_create_superuser(
        self, client: AsyncClient, superuser_token
    ):
        """Test that superuser cannot create another superuser."""
        response = await client.post(
            "/api/v1/users",
            headers=auth_header(superuser_token),
            json={
                "phone_number": "+998905555555",
                "password": "password123",
                "first_name": "Another",
                "last_name": "Superuser",
                "role": "superuser",
            },
        )
        
        assert response.status_code == 403
        assert "don't have permission" in response.json()["detail"]

    async def test_superuser_can_create_director(
        self, client: AsyncClient, db: AsyncSession, superuser_token
    ):
        """Test that superuser can create director."""
        response = await client.post(
            "/api/v1/users",
            headers=auth_header(superuser_token),
            json={
                "phone_number": "+998906666666",
                "password": "password123",
                "first_name": "School",
                "last_name": "Director",
                "role": "director",
            },
        )
        
        assert response.status_code == 201
        assert response.json()["role"] == "director"
        
        # Cleanup
        await db.execute(delete(User).where(User.phone_number == "+998906666666"))
        await db.commit()

    async def test_create_user_duplicate_phone(
        self, client: AsyncClient, owner_token, owner_user
    ):
        """Test creating user with duplicate phone."""
        response = await client.post(
            "/api/v1/users",
            headers=auth_header(owner_token),
            json={
                "phone_number": "+998901111111",  # Already exists
                "password": "password123",
                "first_name": "Duplicate",
                "last_name": "User",
                "role": "staff",
            },
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    async def test_create_user_invalid_phone(self, client: AsyncClient, owner_token):
        """Test creating user with invalid phone format."""
        response = await client.post(
            "/api/v1/users",
            headers=auth_header(owner_token),
            json={
                "phone_number": "invalid",
                "password": "password123",
                "first_name": "Test",
                "last_name": "User",
                "role": "staff",
            },
        )
        
        assert response.status_code == 422


class TestListUsers:
    """Tests for GET /users endpoint."""

    async def test_list_users_as_owner(
        self, client: AsyncClient, owner_token, owner_user, superuser
    ):
        """Test listing users as owner."""
        response = await client.get(
            "/api/v1/users",
            headers=auth_header(owner_token),
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2  # At least owner and superuser

    async def test_list_users_pagination(
        self, client: AsyncClient, owner_token
    ):
        """Test pagination parameters."""
        response = await client.get(
            "/api/v1/users?skip=0&limit=1",
            headers=auth_header(owner_token),
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 1
        assert data["skip"] == 0
        assert data["limit"] == 1

    async def test_list_users_filter_by_role(
        self, client: AsyncClient, owner_token, owner_user
    ):
        """Test filtering by role."""
        response = await client.get(
            "/api/v1/users?role=owner",
            headers=auth_header(owner_token),
        )
        
        assert response.status_code == 200
        data = response.json()
        for user in data["items"]:
            assert user["role"] == "owner"


class TestGetUser:
    """Tests for GET /users/{id} endpoint."""

    async def test_get_user_success(
        self, client: AsyncClient, owner_token, superuser
    ):
        """Test getting a user by ID."""
        response = await client.get(
            f"/api/v1/users/{superuser.id}",
            headers=auth_header(owner_token),
        )
        
        assert response.status_code == 200
        assert response.json()["id"] == str(superuser.id)

    async def test_get_user_not_found(self, client: AsyncClient, owner_token):
        """Test getting non-existent user."""
        fake_id = uuid.uuid4()
        
        response = await client.get(
            f"/api/v1/users/{fake_id}",
            headers=auth_header(owner_token),
        )
        
        assert response.status_code == 404


class TestUpdateUser:
    """Tests for PATCH /users/{id} endpoint."""

    async def test_owner_can_update_superuser(
        self, client: AsyncClient, owner_token, superuser
    ):
        """Test that owner can update superuser."""
        response = await client.patch(
            f"/api/v1/users/{superuser.id}",
            headers=auth_header(owner_token),
            json={"first_name": "UpdatedSuper"},
        )
        
        assert response.status_code == 200
        assert response.json()["first_name"] == "UpdatedSuper"

    async def test_cannot_update_self_via_users_endpoint(
        self, client: AsyncClient, owner_token, owner_user
    ):
        """Test that user cannot update self via /users/{id}."""
        response = await client.patch(
            f"/api/v1/users/{owner_user.id}",
            headers=auth_header(owner_token),
            json={"first_name": "SelfUpdate"},
        )
        
        assert response.status_code == 403


class TestDeleteUser:
    """Tests for DELETE /users/{id} endpoint."""

    async def test_delete_user_success(
        self, client: AsyncClient, db: AsyncSession, owner_token
    ):
        """Test soft deleting a user."""
        # Create a user to delete
        user = User(
            phone_number="+998907777777",
            password_hash=get_password_hash("password123"),
            first_name="ToDelete",
            last_name="User",
            role=Role.STAFF,
            school_id=None,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id
        
        # Delete
        response = await client.delete(
            f"/api/v1/users/{user_id}",
            headers=auth_header(owner_token),
        )
        
        assert response.status_code == 204
        
        # Verify soft deleted
        await db.refresh(user)
        assert user.is_active is False
        
        # Cleanup
        await db.delete(user)
        await db.commit()

    async def test_superuser_cannot_delete_owner(
        self, client: AsyncClient, superuser_token, owner_user
    ):
        """Test that superuser cannot delete owner."""
        response = await client.delete(
            f"/api/v1/users/{owner_user.id}",
            headers=auth_header(superuser_token),
        )
        
        assert response.status_code == 403
