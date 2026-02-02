"""Invoice service - business logic for invoice operations."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discount import Discount, DiscountType, StudentDiscount
from app.models.invoice import Invoice, InvoiceStatus
from app.models.student import Student
from app.schemas.invoice import InvoiceCreate, InvoiceGenerateRequest, InvoiceUpdate


async def get_invoice_by_id(
    db: AsyncSession,
    invoice_id: UUID,
    school_id: UUID | None = None,
) -> Invoice | None:
    """Get invoice by ID, optionally filtered by school."""
    query = select(Invoice).where(Invoice.id == invoice_id)
    if school_id:
        query = query.where(Invoice.school_id == school_id)
    query = query.options(
        selectinload(Invoice.student),
        selectinload(Invoice.payments),
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_invoices(
    db: AsyncSession,
    school_id: UUID | None = None,
    student_id: UUID | None = None,
    status: InvoiceStatus | None = None,
    due_date_from: date | None = None,
    due_date_to: date | None = None,
    period_month: int | None = None,
    period_year: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Invoice], int]:
    """Get invoices with filters."""
    query = select(Invoice)

    # Apply filters
    if school_id:
        query = query.where(Invoice.school_id == school_id)
    if student_id:
        query = query.where(Invoice.student_id == student_id)
    if status:
        query = query.where(Invoice.status == status)
    if due_date_from:
        query = query.where(Invoice.due_date >= due_date_from)
    if due_date_to:
        query = query.where(Invoice.due_date <= due_date_to)
    if period_month and period_year:
        # Filter by period containing this month/year
        period_date = date(period_year, period_month, 1)
        query = query.where(
            and_(
                Invoice.period_start <= period_date,
                Invoice.period_end >= period_date,
            )
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.options(
        selectinload(Invoice.student),
        selectinload(Invoice.payments),
    ).order_by(Invoice.due_date.desc(), Invoice.created_at.desc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    invoices = list(result.scalars().all())

    return invoices, total


async def create_invoice(
    db: AsyncSession,
    invoice_data: InvoiceCreate,
) -> Invoice:
    """Create a new invoice."""
    invoice = Invoice(
        school_id=invoice_data.school_id,
        student_id=invoice_data.student_id,
        period_start=invoice_data.period_start,
        period_end=invoice_data.period_end,
        amount=invoice_data.amount,
        discount_amount=invoice_data.discount_amount,
        due_date=invoice_data.due_date,
        note=invoice_data.note,
        status=InvoiceStatus.PENDING,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    # Load relationships
    return await get_invoice_by_id(db, invoice.id)


async def update_invoice(
    db: AsyncSession,
    invoice: Invoice,
    invoice_data: InvoiceUpdate,
) -> Invoice:
    """Update an existing invoice."""
    update_data = invoice_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(invoice, field, value)

    # Recalculate status if not explicitly set
    if "status" not in update_data:
        invoice.update_status()

    await db.commit()
    await db.refresh(invoice)

    return await get_invoice_by_id(db, invoice.id)


async def delete_invoice(db: AsyncSession, invoice: Invoice) -> None:
    """Delete an invoice."""
    await db.delete(invoice)
    await db.commit()


async def calculate_student_discount(
    db: AsyncSession,
    student_id: UUID,
    base_amount: Decimal,
    invoice_date: date,
) -> Decimal:
    """Calculate total discount for a student based on active discounts."""
    # Get all active discounts for the student
    query = (
        select(Discount)
        .join(StudentDiscount, StudentDiscount.discount_id == Discount.id)
        .where(
            and_(
                StudentDiscount.student_id == student_id,
                Discount.is_active == True,
                or_(Discount.valid_from == None, Discount.valid_from <= invoice_date),
                or_(Discount.valid_until == None, Discount.valid_until >= invoice_date),
            )
        )
    )
    result = await db.execute(query)
    discounts = result.scalars().all()

    total_discount = Decimal("0")
    for discount in discounts:
        if discount.type == DiscountType.PERCENTAGE:
            total_discount += base_amount * (discount.value / 100)
        else:  # FIXED
            total_discount += discount.value

    # Discount cannot exceed the base amount
    return min(total_discount, base_amount)


async def generate_invoices(
    db: AsyncSession,
    request: InvoiceGenerateRequest,
) -> tuple[list[Invoice], int]:
    """
    Generate invoices for students for a given period.
    Returns (generated_invoices, skipped_count).
    """
    # Get students to generate invoices for
    student_query = select(Student).where(
        and_(
            Student.school_id == request.school_id,
            Student.is_active == True,
            Student.graduated_at == None,
        )
    )
    if request.student_ids:
        student_query = student_query.where(Student.id.in_(request.student_ids))

    result = await db.execute(student_query)
    students = result.scalars().all()

    generated_invoices = []
    skipped_count = 0

    for student in students:
        # Check if invoice already exists for this student and period
        existing_query = select(Invoice).where(
            and_(
                Invoice.student_id == student.id,
                Invoice.period_start == request.period_start,
                Invoice.period_end == request.period_end,
            )
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            skipped_count += 1
            continue

        # Calculate discount
        discount_amount = await calculate_student_discount(
            db, student.id, student.monthly_fee, request.period_start
        )

        # Create invoice
        invoice = Invoice(
            school_id=request.school_id,
            student_id=student.id,
            period_start=request.period_start,
            period_end=request.period_end,
            amount=student.monthly_fee,
            discount_amount=discount_amount,
            due_date=request.due_date,
            status=InvoiceStatus.PENDING,
        )
        db.add(invoice)
        generated_invoices.append(invoice)

    await db.commit()

    # Refresh all invoices and load relationships
    refreshed_invoices = []
    for invoice in generated_invoices:
        refreshed = await get_invoice_by_id(db, invoice.id)
        refreshed_invoices.append(refreshed)

    return refreshed_invoices, skipped_count


async def update_overdue_invoices(db: AsyncSession, school_id: UUID | None = None) -> int:
    """
    Update status of overdue invoices.
    Returns count of updated invoices.
    """
    query = select(Invoice).where(
        and_(
            Invoice.status == InvoiceStatus.PENDING,
            Invoice.due_date < date.today(),
        )
    )
    if school_id:
        query = query.where(Invoice.school_id == school_id)

    result = await db.execute(query)
    invoices = result.scalars().all()

    count = 0
    for invoice in invoices:
        invoice.status = InvoiceStatus.OVERDUE
        count += 1

    await db.commit()
    return count


async def get_invoice_summary(
    db: AsyncSession,
    school_id: UUID,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """Get invoice summary statistics for a school."""
    query = select(Invoice).where(Invoice.school_id == school_id)

    if period_start:
        query = query.where(Invoice.period_start >= period_start)
    if period_end:
        query = query.where(Invoice.period_end <= period_end)

    query = query.options(selectinload(Invoice.payments))
    result = await db.execute(query)
    invoices = result.scalars().all()

    total_invoiced = Decimal("0")
    total_discounts = Decimal("0")
    total_paid = Decimal("0")
    total_pending = Decimal("0")
    total_overdue = Decimal("0")

    status_counts = {status: 0 for status in InvoiceStatus}

    for invoice in invoices:
        total_invoiced += invoice.amount
        total_discounts += invoice.discount_amount
        total_paid += invoice.paid_amount

        if invoice.status == InvoiceStatus.PENDING:
            total_pending += invoice.remaining_amount
        elif invoice.status == InvoiceStatus.OVERDUE:
            total_overdue += invoice.remaining_amount

        status_counts[invoice.status] += 1

    return {
        "total_invoiced": total_invoiced,
        "total_discounts": total_discounts,
        "total_after_discounts": total_invoiced - total_discounts,
        "total_paid": total_paid,
        "total_pending": total_pending,
        "total_overdue": total_overdue,
        "invoice_counts": {k.value: v for k, v in status_counts.items()},
    }
