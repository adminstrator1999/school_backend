"""API v1 router aggregating all route modules."""

from fastapi import APIRouter

from app.api.v1.routes import auth, users

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
