"""Tests for Invoices API."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import Discount, DiscountType, StudentDiscount
from app.models.invoice import Invoice, InvoiceStatus
from app.models.school import School
from app.models.student import Student
from tests.conftest import auth_header


# ============== Fixtures ==============


@pytest.fixture
async def school(db: AsyncSession) -> School:
    """Create a test school."""
    school = School(
        name="Test School",
        address="123 Test Street",
        phone="+998901234567",
    )
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


@pytest.fixture
async def student(db: AsyncSession, school: School) -> Student:
    """Create a test student."""
    student = Student(
        school_id=school.id,
        first_name="Test",
        last_name="Student",
        phone="+998901234567",
        parent_first_name="Parent",
        parent_last_name="Test",
        parent_phone_1="+998909876543",
        monthly_fee=Decimal("1000000.00"),
        payment_day=5,
        enrolled_at=date.today() - timedelta(days=30),
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@pytest.fixture
async def student2(db: AsyncSession, school: School) -> Student:
    """Create a second test student."""
    student = Student(
        school_id=school.id,
        first_name="Second",
        last_name="Student",
        phone="+998901234568",
        parent_first_name="Parent2",
        parent_last_name="Test2",
        parent_phone_1="+998909876544",
        monthly_fee=Decimal("1500000.00"),
        payment_day=10,
        enrolled_at=date.today() - timedelta(days=30),
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@pytest.fixture
async def invoice(db: AsyncSession, school: School, student: Student) -> Invoice:
    """Create a test invoice."""
    today = date.today()
    invoice = Invoice(
        school_id=school.id,
        student_id=student.id,
        period_start=today.replace(day=1),
        period_end=(today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
        amount=student.monthly_fee,
        discount_amount=Decimal("0"),
        due_date=today.replace(day=5),
        status=InvoiceStatus.PENDING,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@pytest.fixture
async def discount(db: AsyncSession, school: School) -> Discount:
    """Create a test discount."""
    discount = Discount(
        school_id=school.id,
        name="Sibling Discount",
        type=DiscountType.PERCENTAGE,
        value=Decimal("10.00"),
        is_active=True,
    )
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return discount


@pytest.fixture
async def student_with_discount(
    db: AsyncSession, student: Student, discount: Discount
) -> Student:
    """Assign discount to student and return student."""
    student_discount = StudentDiscount(
        student_id=student.id,
        discount_id=discount.id,
    )
    db.add(student_discount)
    await db.commit()
    return student


# ============== Test Classes ==============


class TestListInvoices:
    """Tests for listing invoices."""

    async def test_list_invoices_empty(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        owner_token: str,
    ):
        """Test listing invoices when none exist."""
        response = await client.get(
            "/api/v1/invoices",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_invoices_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test listing invoices returns data."""
        response = await client.get(
            "/api/v1/invoices",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(invoice.id)

    async def test_list_invoices_filter_by_school(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        school: School,
        owner_token: str,
    ):
        """Test filtering invoices by school."""
        response = await client.get(
            f"/api/v1/invoices?school_id={school.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        # Filter by non-existent school
        response = await client.get(
            f"/api/v1/invoices?school_id={uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_list_invoices_filter_by_student(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        student: Student,
        owner_token: str,
    ):
        """Test filtering invoices by student."""
        response = await client.get(
            f"/api/v1/invoices?student_id={student.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    async def test_list_invoices_filter_by_status(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test filtering invoices by status."""
        response = await client.get(
            "/api/v1/invoices?status=pending",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        response = await client.get(
            "/api/v1/invoices?status=paid",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestCreateInvoice:
    """Tests for creating invoices."""

    async def test_create_invoice_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student: Student,
        owner_token: str,
    ):
        """Test creating an invoice successfully."""
        today = date.today()
        invoice_data = {
            "school_id": str(school.id),
            "student_id": str(student.id),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "amount": "1000000.00",
            "discount_amount": "100000.00",
            "due_date": today.replace(day=15).isoformat(),
            "note": "Test invoice",
        }

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["school_id"] == str(school.id)
        assert data["student_id"] == str(student.id)
        assert Decimal(data["amount"]) == Decimal("1000000.00")
        assert Decimal(data["discount_amount"]) == Decimal("100000.00")
        assert Decimal(data["total_amount"]) == Decimal("900000.00")
        assert data["status"] == "pending"
        assert data["note"] == "Test invoice"

    async def test_create_invoice_invalid_school(
        self,
        client: AsyncClient,
        db: AsyncSession,
        student: Student,
        owner_token: str,
    ):
        """Test creating invoice with non-existent school."""
        today = date.today()
        invoice_data = {
            "school_id": str(uuid4()),
            "student_id": str(student.id),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "amount": "1000000.00",
            "due_date": today.replace(day=15).isoformat(),
        }

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404
        assert "School not found" in response.json()["detail"]

    async def test_create_invoice_invalid_student(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        owner_token: str,
    ):
        """Test creating invoice with non-existent student."""
        today = date.today()
        invoice_data = {
            "school_id": str(school.id),
            "student_id": str(uuid4()),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "amount": "1000000.00",
            "due_date": today.replace(day=15).isoformat(),
        }

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404
        assert "Student not found" in response.json()["detail"]

    async def test_create_invoice_student_wrong_school(
        self,
        client: AsyncClient,
        db: AsyncSession,
        student: Student,
        owner_token: str,
    ):
        """Test creating invoice when student doesn't belong to school."""
        # Create another school
        other_school = School(
            name="Other School",
            address="456 Other Street",
            phone="+998901234568",
        )
        db.add(other_school)
        await db.commit()
        await db.refresh(other_school)

        today = date.today()
        invoice_data = {
            "school_id": str(other_school.id),
            "student_id": str(student.id),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "amount": "1000000.00",
            "due_date": today.replace(day=15).isoformat(),
        }

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 400
        assert "does not belong" in response.json()["detail"]

    async def test_create_invoice_invalid_date_range(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student: Student,
        owner_token: str,
    ):
        """Test creating invoice with invalid date range."""
        today = date.today()
        invoice_data = {
            "school_id": str(school.id),
            "student_id": str(student.id),
            "period_start": today.isoformat(),
            "period_end": (today - timedelta(days=10)).isoformat(),  # End before start
            "amount": "1000000.00",
            "due_date": today.isoformat(),
        }

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 422

    async def test_create_invoice_discount_exceeds_amount(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student: Student,
        owner_token: str,
    ):
        """Test creating invoice where discount exceeds amount."""
        today = date.today()
        invoice_data = {
            "school_id": str(school.id),
            "student_id": str(student.id),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "amount": "1000000.00",
            "discount_amount": "1500000.00",  # More than amount
            "due_date": today.replace(day=15).isoformat(),
        }

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 422


class TestGenerateInvoices:
    """Tests for bulk invoice generation."""

    async def test_generate_invoices_for_all_students(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student: Student,
        student2: Student,
        owner_token: str,
    ):
        """Test generating invoices for all students in a school."""
        today = date.today()
        request_data = {
            "school_id": str(school.id),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "due_date": today.replace(day=15).isoformat(),
        }

        response = await client.post(
            "/api/v1/invoices/generate",
            json=request_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 2
        assert data["skipped_count"] == 0
        assert len(data["invoices"]) == 2

    async def test_generate_invoices_for_specific_students(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student: Student,
        student2: Student,
        owner_token: str,
    ):
        """Test generating invoices for specific students only."""
        today = date.today()
        request_data = {
            "school_id": str(school.id),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "due_date": today.replace(day=15).isoformat(),
            "student_ids": [str(student.id)],  # Only first student
        }

        response = await client.post(
            "/api/v1/invoices/generate",
            json=request_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 1
        assert data["skipped_count"] == 0

    async def test_generate_invoices_skip_existing(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student: Student,
        student2: Student,
        invoice: Invoice,  # Already has an invoice
        owner_token: str,
    ):
        """Test that existing invoices are skipped."""
        request_data = {
            "school_id": str(school.id),
            "period_start": invoice.period_start.isoformat(),
            "period_end": invoice.period_end.isoformat(),
            "due_date": invoice.due_date.isoformat(),
        }

        response = await client.post(
            "/api/v1/invoices/generate",
            json=request_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 1  # Only student2
        assert data["skipped_count"] == 1  # student1 already has invoice

    async def test_generate_invoices_with_discount(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student_with_discount: Student,
        owner_token: str,
    ):
        """Test that discounts are applied during generation."""
        today = date.today()
        request_data = {
            "school_id": str(school.id),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "due_date": today.replace(day=15).isoformat(),
            "student_ids": [str(student_with_discount.id)],
        }

        response = await client.post(
            "/api/v1/invoices/generate",
            json=request_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated_count"] == 1

        # Check discount was applied (10% of 1,000,000 = 100,000)
        invoice = data["invoices"][0]
        assert Decimal(invoice["amount"]) == Decimal("1000000.00")
        assert Decimal(invoice["discount_amount"]) == Decimal("100000.00")
        assert Decimal(invoice["total_amount"]) == Decimal("900000.00")

    async def test_generate_invoices_invalid_school(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test generating invoices for non-existent school."""
        today = date.today()
        request_data = {
            "school_id": str(uuid4()),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "due_date": today.replace(day=15).isoformat(),
        }

        response = await client.post(
            "/api/v1/invoices/generate",
            json=request_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestGetInvoice:
    """Tests for getting a single invoice."""

    async def test_get_invoice_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test getting an invoice by ID."""
        response = await client.get(
            f"/api/v1/invoices/{invoice.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invoice.id)
        assert data["status"] == "pending"
        assert "student" in data
        assert "payments" in data

    async def test_get_invoice_not_found(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test getting non-existent invoice."""
        response = await client.get(
            f"/api/v1/invoices/{uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestUpdateInvoice:
    """Tests for updating invoices."""

    async def test_update_invoice_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test updating an invoice."""
        update_data = {
            "amount": "1200000.00",
            "note": "Updated note",
        }

        response = await client.patch(
            f"/api/v1/invoices/{invoice.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["amount"]) == Decimal("1200000.00")
        assert data["note"] == "Updated note"

    async def test_update_invoice_status(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test updating invoice status."""
        update_data = {"status": "paid"}

        response = await client.patch(
            f"/api/v1/invoices/{invoice.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "paid"

    async def test_update_invoice_discount_exceeds_amount(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test updating with discount exceeding amount."""
        update_data = {
            "discount_amount": "2000000.00",  # More than invoice amount
        }

        response = await client.patch(
            f"/api/v1/invoices/{invoice.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 400
        assert "cannot exceed" in response.json()["detail"]

    async def test_update_invoice_not_found(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test updating non-existent invoice."""
        response = await client.patch(
            f"/api/v1/invoices/{uuid4()}",
            json={"note": "test"},
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestDeleteInvoice:
    """Tests for deleting invoices."""

    async def test_delete_invoice_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test deleting an invoice."""
        response = await client.delete(
            f"/api/v1/invoices/{invoice.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 204

        # Verify it's deleted
        response = await client.get(
            f"/api/v1/invoices/{invoice.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404

    async def test_delete_invoice_not_found(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test deleting non-existent invoice."""
        response = await client.delete(
            f"/api/v1/invoices/{uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestInvoiceSummary:
    """Tests for invoice summary endpoint."""

    async def test_get_summary(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test getting invoice summary."""
        response = await client.get(
            f"/api/v1/invoices/summary?school_id={school.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_invoiced" in data
        assert "total_discounts" in data
        assert "total_paid" in data
        assert "invoice_counts" in data

    async def test_get_summary_invalid_school(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test getting summary for non-existent school."""
        response = await client.get(
            f"/api/v1/invoices/summary?school_id={uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestUpdateOverdueInvoices:
    """Tests for updating overdue invoices."""

    async def test_update_overdue_invoices(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student: Student,
        owner_token: str,
    ):
        """Test marking overdue invoices."""
        # Create an overdue invoice
        past_date = date.today() - timedelta(days=30)
        overdue_invoice = Invoice(
            school_id=school.id,
            student_id=student.id,
            period_start=past_date.replace(day=1),
            period_end=past_date.replace(day=28),
            amount=Decimal("1000000.00"),
            discount_amount=Decimal("0"),
            due_date=past_date.replace(day=15),  # Due date in the past
            status=InvoiceStatus.PENDING,
        )
        db.add(overdue_invoice)
        await db.commit()
        await db.refresh(overdue_invoice)

        response = await client.post(
            "/api/v1/invoices/update-overdue",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] >= 1

        # Verify status changed
        check_response = await client.get(
            f"/api/v1/invoices/{overdue_invoice.id}",
            headers=auth_header(owner_token),
        )
        assert check_response.json()["status"] == "overdue"


class TestSQLInjection:
    """Tests for SQL injection prevention."""

    async def test_filter_sql_injection(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test SQL injection in filter parameters."""
        response = await client.get(
            "/api/v1/invoices?status=pending' OR '1'='1",
            headers=auth_header(owner_token),
        )
        # Should fail validation or return no results, not crash
        assert response.status_code in [200, 422]

    async def test_create_invoice_sql_injection(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        student: Student,
        owner_token: str,
    ):
        """Test SQL injection in note field."""
        today = date.today()
        invoice_data = {
            "school_id": str(school.id),
            "student_id": str(student.id),
            "period_start": today.replace(day=1).isoformat(),
            "period_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "amount": "1000000.00",
            "due_date": today.replace(day=15).isoformat(),
            "note": "'; DROP TABLE invoices; --",
        }

        response = await client.post(
            "/api/v1/invoices",
            json=invoice_data,
            headers=auth_header(owner_token),
        )
        # Should succeed but not execute the injection
        assert response.status_code == 201
        assert response.json()["note"] == "'; DROP TABLE invoices; --"
