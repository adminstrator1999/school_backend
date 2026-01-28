"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


class TestLogin:
    """Tests for login endpoints."""

    async def test_login_success(self, client: AsyncClient, owner_user):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "+998901111111", "password": "password123"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, owner_user):
        """Test login with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "+998901111111", "password": "wrongpassword"},
        )
        
        assert response.status_code == 401
        assert "Incorrect phone number or password" in response.json()["detail"]

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "+998909999999", "password": "password123"},
        )
        
        assert response.status_code == 401

    async def test_login_invalid_phone_format(self, client: AsyncClient):
        """Test login with invalid phone format."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "12345", "password": "password123"},
        )
        
        assert response.status_code == 422  # Validation error

    async def test_login_normalizes_phone(self, client: AsyncClient, owner_user):
        """Test that login normalizes phone number format."""
        # Login with spaces in phone number
        response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "+998 90 111 11 11", "password": "password123"},
        )
        
        assert response.status_code == 200


class TestRefresh:
    """Tests for token refresh endpoint."""

    async def test_refresh_success(self, client: AsyncClient, owner_user):
        """Test successful token refresh."""
        # First login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"phone_number": "+998901111111", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh tokens
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Test refresh with invalid token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        
        assert response.status_code == 401

    async def test_refresh_with_access_token(self, client: AsyncClient, owner_token):
        """Test that access token cannot be used for refresh."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": owner_token},  # Using access token
        )
        
        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]
