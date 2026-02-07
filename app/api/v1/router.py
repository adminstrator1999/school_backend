"""API v1 router aggregating all route modules."""

from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    classes,
    discounts,
    employees,
    expense_categories,
    expenses,
    invoices,
    payments,
    positions,
    recurring_expenses,
    reports,
    schools,
    students,
    uploads,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(schools.router)
api_router.include_router(classes.router)
api_router.include_router(students.router)
api_router.include_router(positions.router)
api_router.include_router(employees.router)
api_router.include_router(discounts.router)
api_router.include_router(invoices.router)
api_router.include_router(payments.router)
api_router.include_router(expense_categories.router)
api_router.include_router(expenses.router)
api_router.include_router(recurring_expenses.router)
api_router.include_router(reports.router)
api_router.include_router(uploads.router)

