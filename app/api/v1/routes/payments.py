"""Payment routes."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.permissions import Role
from app.models.invoice import PaymentMethod
from app.schemas.payment import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentSummary,
    PaymentUpdate,
)
from app.services import invoice as invoice_service
from app.services import payment as payment_service

router = APIRouter(prefix="/payments", tags=["Payments"])


def can_manage_payments(user) -> bool:
    """Check if user has permission to manage payments."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
        Role.SHAREHOLDER,
        Role.ACCOUNTANT,
    )


def can_delete_payments(user) -> bool:
    """Check if user has permission to delete payments."""
    return user.role in (
        Role.OWNER,
        Role.SUPERUSER,
        Role.DIRECTOR,
    )


def _build_payment_response(payment) -> PaymentResponse:
    """Build payment response with nested objects."""
    invoice_info = None
    if payment.invoice:
        # Handle status as either enum or string
        status = payment.invoice.status
        if hasattr(status, 'value'):
            status = status.value
        invoice_info = {
            "id": payment.invoice.id,
            "student_id": payment.invoice.student_id,
            "period_start": payment.invoice.period_start,
            "period_end": payment.invoice.period_end,
            "total_amount": payment.invoice.total_amount,
            "status": status,
        }

    received_by_info = None
    if payment.received_by:
        received_by_info = {
            "id": payment.received_by.id,
            "first_name": payment.received_by.first_name,
            "last_name": payment.received_by.last_name,
        }

    return PaymentResponse(
        id=payment.id,
        school_id=payment.school_id,
        invoice_id=payment.invoice_id,
        invoice=invoice_info,
        amount=payment.amount,
        payment_method=payment.payment_method,
        paid_at=payment.paid_at,
        received_by_id=payment.received_by_id,
        received_by=received_by_info,
        note=payment.note,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


@router.get("", response_model=PaymentListResponse)
async def list_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID | None = Query(None, description="Filter by school ID"),
    invoice_id: UUID | None = Query(None, description="Filter by invoice ID"),
    payment_method: PaymentMethod | None = Query(None, description="Filter by payment method"),
    date_from: date | None = Query(None, description="Filter by date from"),
    date_to: date | None = Query(None, description="Filter by date to"),
    received_by_id: UUID | None = Query(None, description="Filter by receiver user ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of records"),
) -> PaymentListResponse:
    """
    List payments with optional filters.
    
    - **school_id**: Filter by school
    - **invoice_id**: Filter by invoice
    - **payment_method**: Filter by method (cash, card, transfer)
    - **date_from/to**: Filter by payment date range
    - **received_by_id**: Filter by user who received payment
    """
    if not can_manage_payments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Non-superusers can only see their own school's payments
    if not current_user.is_superuser:
        school_id = current_user.school_id

    payments, total = await payment_service.get_payments(
        db,
        school_id=school_id,
        invoice_id=invoice_id,
        payment_method=payment_method,
        date_from=date_from,
        date_to=date_to,
        received_by_id=received_by_id,
        skip=skip,
        limit=limit,
    )

    return PaymentListResponse(
        items=[_build_payment_response(p) for p in payments],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> PaymentResponse:
    """
    Create a new payment for an invoice.
    
    The invoice status will be automatically updated based on total payments:
    - **PAID**: When total payments >= invoice total
    - **PARTIAL**: When payments exist but less than total
    - **PENDING/OVERDUE**: When no payments
    """
    if not can_manage_payments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Verify invoice exists
    invoice = await invoice_service.get_invoice_by_id(db, payment_data.invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Non-superusers can only add payments to their school's invoices
    if not current_user.is_superuser and invoice.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot add payment to invoice from another school",
        )

    # Validate payment amount doesn't exceed remaining
    if payment_data.amount > invoice.remaining_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount ({payment_data.amount}) exceeds remaining balance ({invoice.remaining_amount})",
        )

    payment = await payment_service.create_payment(
        db,
        payment_data,
        received_by_id=current_user.id,
        school_id=invoice.school_id,
    )
    return _build_payment_response(payment)


@router.get("/summary", response_model=PaymentSummary)
async def get_payment_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    school_id: UUID = Query(..., description="School ID"),
    date_from: date | None = Query(None, description="Start date"),
    date_to: date | None = Query(None, description="End date"),
) -> PaymentSummary:
    """Get payment summary statistics for a school."""
    if not can_manage_payments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Non-superusers can only see their own school's summary
    if not current_user.is_superuser and school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view summary for another school",
        )

    summary = await payment_service.get_payment_summary(db, school_id, date_from, date_to)
    return PaymentSummary(**summary)


@router.get("/invoice/{invoice_id}", response_model=list[PaymentResponse])
async def get_payments_for_invoice(
    invoice_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> list[PaymentResponse]:
    """Get all payments for a specific invoice."""
    if not can_manage_payments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    # Verify invoice exists
    invoice = await invoice_service.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Non-superusers can only see their own school's payments
    if not current_user.is_superuser and invoice.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view payments for invoice from another school",
        )

    payments = await payment_service.get_payments_for_invoice(db, invoice_id)
    return [_build_payment_response(p) for p in payments]


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> PaymentResponse:
    """Get a payment by ID."""
    if not can_manage_payments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    payment = await payment_service.get_payment_by_id(db, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Non-superusers can only see their own school's payments
    if not current_user.is_superuser and payment.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view payment from another school",
        )

    return _build_payment_response(payment)


@router.patch("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: UUID,
    payment_data: PaymentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> PaymentResponse:
    """Update a payment."""
    if not can_manage_payments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    payment = await payment_service.get_payment_by_id(db, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Non-superusers can only update their own school's payments
    if not current_user.is_superuser and payment.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update payment from another school",
        )

    # Validate new amount if provided
    if payment_data.amount is not None:
        invoice = await invoice_service.get_invoice_by_id(db, payment.invoice_id)
        if invoice:
            # Calculate remaining (excluding current payment)
            other_payments = invoice.paid_amount - payment.amount
            new_remaining = invoice.total_amount - other_payments
            if payment_data.amount > new_remaining:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Payment amount ({payment_data.amount}) exceeds remaining balance ({new_remaining})",
                )

    updated = await payment_service.update_payment(db, payment, payment_data)
    return _build_payment_response(updated)


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    """
    Delete a payment.
    
    Note: This will update the associated invoice status accordingly.
    """
    if not can_delete_payments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )

    payment = await payment_service.get_payment_by_id(db, payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Non-superusers can only delete their own school's payments
    if not current_user.is_superuser and payment.school_id != current_user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete payment from another school",
        )

    await payment_service.delete_payment(db, payment)
