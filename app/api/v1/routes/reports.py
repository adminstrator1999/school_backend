"""Report API routes."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import Role
from app.schemas.report import (
    ExpenseReport,
    FinancialSummary,
    MonthlyTrendReport,
    PaymentReport,
)
from app.services import report as report_service
from app.services import school as school_service

router = APIRouter(prefix="/reports", tags=["Reports"])


# ============== Helper Functions ==============


def can_view_reports(user) -> bool:
    """Check if user has permission to view reports."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.SHAREHOLDER,
        Role.ACCOUNTANT,
    )


# ============== Endpoints ==============


@router.get("/financial-summary", response_model=FinancialSummary)
async def get_financial_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID = Query(..., description="School ID"),
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
) -> FinancialSummary:
    """
    Get financial summary for a school.
    
    Returns income (invoiced, collected, outstanding by payment method),
    expenses (total, by category), and net income.
    """
    if not can_view_reports(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view reports",
        )

    # Non-superusers can only view their own school's reports
    if not current_user.is_superuser:
        if school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view reports from other schools",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Validate date range
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to must be after date_from",
        )

    summary = await report_service.get_financial_summary(db, school_id, date_from, date_to)
    return FinancialSummary(**summary)


@router.get("/payments", response_model=PaymentReport)
async def get_payment_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID = Query(..., description="School ID"),
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
) -> PaymentReport:
    """
    Get payment report for a school.
    
    Returns invoice status counts, collection rate, and top debtors.
    """
    if not can_view_reports(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view reports",
        )

    # Non-superusers can only view their own school's reports
    if not current_user.is_superuser:
        if school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view reports from other schools",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Validate date range
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to must be after date_from",
        )

    report = await report_service.get_payment_report(db, school_id, date_from, date_to)
    return PaymentReport(**report)


@router.get("/expenses", response_model=ExpenseReport)
async def get_expense_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID = Query(..., description="School ID"),
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
) -> ExpenseReport:
    """
    Get expense report for a school.
    
    Returns total expenses, breakdown by category with percentages.
    """
    if not can_view_reports(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view reports",
        )

    # Non-superusers can only view their own school's reports
    if not current_user.is_superuser:
        if school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view reports from other schools",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Validate date range
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to must be after date_from",
        )

    report = await report_service.get_expense_report(db, school_id, date_from, date_to)
    return ExpenseReport(**report)


@router.get("/monthly-trend", response_model=MonthlyTrendReport)
async def get_monthly_trend(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID = Query(..., description="School ID"),
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
) -> MonthlyTrendReport:
    """
    Get monthly income/expense trend for a school.
    
    Returns income, expenses, and net for each month in the range.
    """
    if not can_view_reports(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view reports",
        )

    # Non-superusers can only view their own school's reports
    if not current_user.is_superuser:
        if school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view reports from other schools",
            )

    # Verify school exists
    school = await school_service.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Validate date range
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to must be after date_from",
        )

    report = await report_service.get_monthly_trend(db, school_id, date_from, date_to)
    return MonthlyTrendReport(**report)
