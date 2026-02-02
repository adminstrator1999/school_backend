"""Payment service - business logic for payment operations."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.schemas.payment import PaymentCreate, PaymentUpdate


async def get_payment_by_id(
    db: AsyncSession,
    payment_id: UUID,
    school_id: UUID | None = None,
) -> Payment | None:
    """Get payment by ID, optionally filtered by school."""
    query = select(Payment).where(Payment.id == payment_id)
    if school_id:
        query = query.where(Payment.school_id == school_id)
    query = query.options(
        selectinload(Payment.invoice),
        selectinload(Payment.received_by),
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_payments(
    db: AsyncSession,
    school_id: UUID | None = None,
    invoice_id: UUID | None = None,
    payment_method: PaymentMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    received_by_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Payment], int]:
    """Get payments with filters."""
    query = select(Payment)

    # Apply filters
    if school_id:
        query = query.where(Payment.school_id == school_id)
    if invoice_id:
        query = query.where(Payment.invoice_id == invoice_id)
    if payment_method:
        query = query.where(Payment.payment_method == payment_method)
    if date_from:
        query = query.where(func.date(Payment.paid_at) >= date_from)
    if date_to:
        query = query.where(func.date(Payment.paid_at) <= date_to)
    if received_by_id:
        query = query.where(Payment.received_by_id == received_by_id)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.options(
        selectinload(Payment.invoice),
        selectinload(Payment.received_by),
    ).order_by(Payment.paid_at.desc(), Payment.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    payments = list(result.scalars().all())

    return payments, total


async def create_payment(
    db: AsyncSession,
    payment_data: PaymentCreate,
    received_by_id: UUID,
    school_id: UUID,
) -> Payment:
    """Create a new payment and update invoice status."""
    payment = Payment(
        school_id=school_id,
        invoice_id=payment_data.invoice_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        received_by_id=received_by_id,
        note=payment_data.note,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    # Update invoice status
    await update_invoice_status(db, payment_data.invoice_id)

    # Load relationships
    return await get_payment_by_id(db, payment.id)


async def update_payment(
    db: AsyncSession,
    payment: Payment,
    payment_data: PaymentUpdate,
) -> Payment:
    """Update an existing payment."""
    old_invoice_id = payment.invoice_id
    update_data = payment_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(payment, field, value)

    await db.commit()
    await db.refresh(payment)

    # Update invoice status
    await update_invoice_status(db, old_invoice_id)

    return await get_payment_by_id(db, payment.id)


async def delete_payment(db: AsyncSession, payment: Payment) -> None:
    """Delete a payment and update invoice status."""
    invoice_id = payment.invoice_id
    await db.delete(payment)
    await db.commit()

    # Update invoice status after deletion
    await update_invoice_status(db, invoice_id)


async def update_invoice_status(db: AsyncSession, invoice_id: UUID) -> None:
    """Update invoice status based on payments."""
    # Get invoice
    invoice_query = select(Invoice).where(Invoice.id == invoice_id)
    invoice_result = await db.execute(invoice_query)
    invoice = invoice_result.scalar_one_or_none()

    if not invoice:
        return

    # Calculate total paid directly from database (avoids session caching issues)
    payments_query = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.invoice_id == invoice_id
    )
    payments_result = await db.execute(payments_query)
    total_paid = payments_result.scalar() or Decimal(0)
    
    total_due = invoice.amount - invoice.discount_amount

    # Determine new status
    if total_paid >= total_due:
        new_status = InvoiceStatus.PAID
    elif total_paid > 0:
        new_status = InvoiceStatus.PARTIAL
    elif date.today() > invoice.due_date:
        new_status = InvoiceStatus.OVERDUE
    else:
        new_status = InvoiceStatus.PENDING

    # Use execute to update to avoid session caching issues
    from sqlalchemy import update
    await db.execute(
        update(Invoice).where(Invoice.id == invoice_id).values(status=new_status)
    )
    await db.commit()


async def get_payment_summary(
    db: AsyncSession,
    school_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Get payment summary statistics for a school."""
    query = select(Payment).where(Payment.school_id == school_id)

    if date_from:
        query = query.where(func.date(Payment.paid_at) >= date_from)
    if date_to:
        query = query.where(func.date(Payment.paid_at) <= date_to)

    result = await db.execute(query)
    payments = result.scalars().all()

    total_amount = Decimal("0")
    by_method: dict[str, Decimal] = {}

    for payment in payments:
        total_amount += payment.amount
        method = payment.payment_method
        if hasattr(method, "value"):
            method = method.value
        by_method[method] = by_method.get(method, Decimal("0")) + payment.amount

    return {
        "total_payments": len(payments),
        "total_amount": total_amount,
        "by_method": by_method,
    }


async def get_payments_for_invoice(
    db: AsyncSession,
    invoice_id: UUID,
) -> list[Payment]:
    """Get all payments for a specific invoice."""
    query = select(Payment).where(Payment.invoice_id == invoice_id).options(
        selectinload(Payment.received_by),
    ).order_by(Payment.paid_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())
