"""Invoice routes."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import Role
from app.models.invoice import InvoiceStatus
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceGenerateRequest,
    InvoiceGenerateResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
)
from app.services import invoice as invoice_service
from app.services import school as school_service
from app.services import student as student_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def can_manage_invoices(user) -> bool:
    """Check if user has permission to manage invoices."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.SHAREHOLDER,
        Role.ACCOUNTANT,
    )


def can_delete_invoices(user) -> bool:
    """Check if user has permission to delete invoices."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
    )


def _build_invoice_response(invoice) -> InvoiceResponse:
    """Build invoice response with computed properties."""
    return InvoiceResponse(
        id=invoice.id,
        school_id=invoice.school_id,
        student_id=invoice.student_id,
        student=invoice.student if invoice.student else None,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        amount=invoice.amount,
        discount_amount=invoice.discount_amount,
        total_amount=invoice.total_amount,
        paid_amount=invoice.paid_amount,
        remaining_amount=invoice.remaining_amount,
        due_date=invoice.due_date,
        status=invoice.status,
        note=invoice.note,
        payments=invoice.payments if invoice.payments else [],
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    student_id: UUID | None = Query(None, description="Filter by student ID"),
    invoice_status: InvoiceStatus | None = Query(None, alias="status", description="Filter by status"),
    due_date_from: date | None = Query(None, description="Filter by due date from"),
    due_date_to: date | None = Query(None, description="Filter by due date to"),
    period_month: int | None = Query(None, ge=1, le=12, description="Filter by period month"),
    period_year: int | None = Query(None, ge=2000, le=2100, description="Filter by period year"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of records"),
) -> InvoiceListResponse:
    """
    List invoices with optional filters.
    
    - **school_id**: Filter by school
    - **student_id**: Filter by student
    - **status**: Filter by status (pending, partial, paid, overdue)
    - **due_date_from/to**: Filter by due date range
    - **period_month/year**: Filter by invoice period
    """
    if not can_manage_invoices(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Non-superusers can only see their own school's invoices
    if not current_user.is_superuser:
        school_id = current_user.school_id

    invoices, total = await invoice_service.get_invoices(
        db,
        school_id=school_id,
        student_id=student_id,
        status=invoice_status,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        period_month=period_month,
        period_year=period_year,
        skip=skip,
        limit=limit,
    )

    return InvoiceListResponse(
        items=[_build_invoice_response(i) for i in invoices],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: InvoiceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> InvoiceResponse:
    """Create a new invoice manually."""
    if not can_manage_invoices(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Verify school exists
    school = await school_service.get_school_by_id(db, invoice_data.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    # Verify student exists and belongs to school
    student = await student_service.get_student_by_id(db, invoice_data.student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    if student.school_id != invoice_data.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student does not belong to the specified school",
        )

    invoice = await invoice_service.create_invoice(db, invoice_data)
    return _build_invoice_response(invoice)


@router.post("/generate", response_model=InvoiceGenerateResponse)
async def generate_invoices(
    request: InvoiceGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> InvoiceGenerateResponse:
    """
    Generate invoices for multiple students.
    
    - If **student_ids** is provided, generate for those students only
    - If **student_ids** is null/empty, generate for all active students in the school
    - Automatically applies discounts based on student's assigned discounts
    - Skips students who already have invoices for the specified period
    """
    if not can_manage_invoices(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Verify school exists
    school = await school_service.get_school_by_id(db, request.school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    invoices, skipped = await invoice_service.generate_invoices(db, request)

    return InvoiceGenerateResponse(
        generated_count=len(invoices),
        skipped_count=skipped,
        invoices=[_build_invoice_response(i) for i in invoices],
    )


@router.get("/summary")
async def get_invoice_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID = Query(..., description="School ID"),
    period_start: date | None = Query(None, description="Period start date"),
    period_end: date | None = Query(None, description="Period end date"),
) -> dict:
    """Get invoice summary statistics for a school."""
    if not can_manage_invoices(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Verify school exists
    school = await school_service.get_school_by_id(db, school_id)
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="School not found",
        )

    return await invoice_service.get_invoice_summary(db, school_id, period_start, period_end)


@router.post("/update-overdue")
async def update_overdue_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="School ID (optional)"),
) -> dict:
    """Update status of overdue invoices to 'overdue'."""
    if current_user.role not in (Role.OWNER, Role.SUPERUSER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    count = await invoice_service.update_overdue_invoices(db, school_id)
    return {"updated_count": count}


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> InvoiceResponse:
    """Get an invoice by ID."""
    if not can_manage_invoices(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    invoice = await invoice_service.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return _build_invoice_response(invoice)


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    invoice_data: InvoiceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> InvoiceResponse:
    """Update an invoice."""
    if not can_manage_invoices(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    invoice = await invoice_service.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Validate discount doesn't exceed amount
    new_amount = invoice_data.amount if invoice_data.amount else invoice.amount
    new_discount = invoice_data.discount_amount if invoice_data.discount_amount is not None else invoice.discount_amount
    if new_discount > new_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount amount cannot exceed invoice amount",
        )

    updated = await invoice_service.update_invoice(db, invoice, invoice_data)
    return _build_invoice_response(updated)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    """
    Delete an invoice.
    
    Note: This will also delete all associated payments.
    """
    if not can_delete_invoices(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    invoice = await invoice_service.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Don't allow deleting invoices with payments
    if invoice.payments and len(invoice.payments) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete invoice with existing payments. Delete payments first.",
        )

    await invoice_service.delete_invoice(db, invoice)
