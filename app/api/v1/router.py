"""API v1 router aggregating all route modules."""

from fastapi import APIRouter

from app.api.v1.routes import auth, classes, discounts, employees, positions, schools, students, users

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(schools.router)
api_router.include_router(classes.router)
api_router.include_router(students.router)
api_router.include_router(positions.router)
api_router.include_router(employees.router)
api_router.include_router(discounts.router)
