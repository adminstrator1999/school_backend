"""Tests for Payments API."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.models.school import School
from app.models.student import Student
from app.models.user import User
from app.core.permissions import Role
from app.core.security import get_password_hash
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
async def invoice(db: AsyncSession, school: School, student: Student) -> Invoice:
    """Create a test invoice."""
    today = date.today()
    invoice = Invoice(
        school_id=school.id,
        student_id=student.id,
        period_start=today.replace(day=1),
        period_end=(today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
        amount=Decimal("1000000.00"),
        discount_amount=Decimal("0"),
        due_date=today.replace(day=15),
        status=InvoiceStatus.PENDING,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@pytest.fixture
async def accountant_user(db: AsyncSession, school: School) -> User:
    """Create an accountant user."""
    user = User(
        phone_number="+998903333333",
        password_hash=get_password_hash("password123"),
        first_name="Accountant",
        last_name="User",
        role=Role.ACCOUNTANT,
        school_id=school.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def payment(
    db: AsyncSession, school: School, invoice: Invoice, owner_user: User
) -> Payment:
    """Create a test payment."""
    payment = Payment(
        school_id=school.id,
        invoice_id=invoice.id,
        amount=Decimal("500000.00"),
        payment_method=PaymentMethod.CASH,
        received_by_id=owner_user.id,
        note="Test payment",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


# ============== Test Classes ==============


class TestListPayments:
    """Tests for listing payments."""

    async def test_list_payments_empty(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        owner_token: str,
    ):
        """Test listing payments when none exist."""
        response = await client.get(
            "/api/v1/payments",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_payments_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        payment: Payment,
        owner_token: str,
    ):
        """Test listing payments returns data."""
        response = await client.get(
            "/api/v1/payments",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(payment.id)

    async def test_list_payments_filter_by_invoice(
        self,
        client: AsyncClient,
        db: AsyncSession,
        payment: Payment,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test filtering payments by invoice."""
        response = await client.get(
            f"/api/v1/payments?invoice_id={invoice.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        # Filter by non-existent invoice
        response = await client.get(
            f"/api/v1/payments?invoice_id={uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_list_payments_filter_by_method(
        self,
        client: AsyncClient,
        db: AsyncSession,
        payment: Payment,
        owner_token: str,
    ):
        """Test filtering payments by payment method."""
        response = await client.get(
            "/api/v1/payments?payment_method=cash",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        response = await client.get(
            "/api/v1/payments?payment_method=card",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestCreatePayment:
    """Tests for creating payments."""

    async def test_create_payment_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test creating a payment successfully."""
        payment_data = {
            "invoice_id": str(invoice.id),
            "amount": "500000.00",
            "payment_method": "cash",
            "note": "Partial payment",
        }

        response = await client.post(
            "/api/v1/payments",
            json=payment_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["invoice_id"] == str(invoice.id)
        assert Decimal(data["amount"]) == Decimal("500000.00")
        assert data["payment_method"] == "cash"
        assert data["note"] == "Partial payment"

    async def test_create_payment_updates_invoice_status_partial(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test that partial payment updates invoice status to partial."""
        payment_data = {
            "invoice_id": str(invoice.id),
            "amount": "500000.00",
            "payment_method": "cash",
        }

        response = await client.post(
            "/api/v1/payments",
            json=payment_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 201

        # Check invoice status
        invoice_response = await client.get(
            f"/api/v1/invoices/{invoice.id}",
            headers=auth_header(owner_token),
        )
        assert invoice_response.json()["status"] == "partial"

    async def test_create_payment_updates_invoice_status_paid(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test that full payment updates invoice status to paid."""
        payment_data = {
            "invoice_id": str(invoice.id),
            "amount": "1000000.00",  # Full amount
            "payment_method": "transfer",
        }

        response = await client.post(
            "/api/v1/payments",
            json=payment_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 201

        # Check invoice status
        invoice_response = await client.get(
            f"/api/v1/invoices/{invoice.id}",
            headers=auth_header(owner_token),
        )
        assert invoice_response.json()["status"] == "paid"

    async def test_create_payment_different_methods(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test creating payments with different methods."""
        for method in ["cash", "card", "transfer"]:
            # Create a new invoice for each test
            today = date.today()
            new_invoice = Invoice(
                school_id=invoice.school_id,
                student_id=invoice.student_id,
                period_start=today.replace(day=1),
                period_end=today.replace(day=28),
                amount=Decimal("100000.00"),
                discount_amount=Decimal("0"),
                due_date=today.replace(day=15),
                status=InvoiceStatus.PENDING,
            )
            db.add(new_invoice)
            await db.commit()
            await db.refresh(new_invoice)

            payment_data = {
                "invoice_id": str(new_invoice.id),
                "amount": "100000.00",
                "payment_method": method,
            }

            response = await client.post(
                "/api/v1/payments",
                json=payment_data,
                headers=auth_header(owner_token),
            )
            assert response.status_code == 201
            assert response.json()["payment_method"] == method

    async def test_create_payment_invalid_invoice(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test creating payment with non-existent invoice."""
        payment_data = {
            "invoice_id": str(uuid4()),
            "amount": "500000.00",
            "payment_method": "cash",
        }

        response = await client.post(
            "/api/v1/payments",
            json=payment_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404
        assert "Invoice not found" in response.json()["detail"]

    async def test_create_payment_exceeds_remaining(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test creating payment that exceeds remaining balance."""
        payment_data = {
            "invoice_id": str(invoice.id),
            "amount": "1500000.00",  # More than invoice total
            "payment_method": "cash",
        }

        response = await client.post(
            "/api/v1/payments",
            json=payment_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 400
        assert "exceeds remaining balance" in response.json()["detail"]


class TestGetPayment:
    """Tests for getting a single payment."""

    async def test_get_payment_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        payment: Payment,
        owner_token: str,
    ):
        """Test getting a payment by ID."""
        response = await client.get(
            f"/api/v1/payments/{payment.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(payment.id)
        assert "invoice" in data
        assert "received_by" in data

    async def test_get_payment_not_found(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test getting non-existent payment."""
        response = await client.get(
            f"/api/v1/payments/{uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestGetPaymentsForInvoice:
    """Tests for getting payments by invoice."""

    async def test_get_payments_for_invoice(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        payment: Payment,
        owner_token: str,
    ):
        """Test getting all payments for an invoice."""
        response = await client.get(
            f"/api/v1/payments/invoice/{invoice.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(payment.id)

    async def test_get_payments_for_invoice_not_found(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test getting payments for non-existent invoice."""
        response = await client.get(
            f"/api/v1/payments/invoice/{uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestUpdatePayment:
    """Tests for updating payments."""

    async def test_update_payment_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        payment: Payment,
        owner_token: str,
    ):
        """Test updating a payment."""
        update_data = {
            "amount": "600000.00",
            "note": "Updated note",
        }

        response = await client.patch(
            f"/api/v1/payments/{payment.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["amount"]) == Decimal("600000.00")
        assert data["note"] == "Updated note"

    async def test_update_payment_method(
        self,
        client: AsyncClient,
        db: AsyncSession,
        payment: Payment,
        owner_token: str,
    ):
        """Test updating payment method."""
        update_data = {"payment_method": "card"}

        response = await client.patch(
            f"/api/v1/payments/{payment.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        assert response.json()["payment_method"] == "card"

    async def test_update_payment_exceeds_remaining(
        self,
        client: AsyncClient,
        db: AsyncSession,
        payment: Payment,
        owner_token: str,
    ):
        """Test updating payment to exceed remaining balance."""
        update_data = {
            "amount": "1500000.00",  # More than invoice total
        }

        response = await client.patch(
            f"/api/v1/payments/{payment.id}",
            json=update_data,
            headers=auth_header(owner_token),
        )
        assert response.status_code == 400
        assert "exceeds remaining balance" in response.json()["detail"]

    async def test_update_payment_not_found(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test updating non-existent payment."""
        response = await client.patch(
            f"/api/v1/payments/{uuid4()}",
            json={"note": "test"},
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestDeletePayment:
    """Tests for deleting payments."""

    async def test_delete_payment_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        payment: Payment,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test deleting a payment."""
        response = await client.delete(
            f"/api/v1/payments/{payment.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 204

        # Verify it's deleted
        response = await client.get(
            f"/api/v1/payments/{payment.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404

    async def test_delete_payment_updates_invoice_status(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test that deleting payment updates invoice status."""
        # First create a payment that makes invoice partial
        payment_data = {
            "invoice_id": str(invoice.id),
            "amount": "500000.00",
            "payment_method": "cash",
        }
        create_response = await client.post(
            "/api/v1/payments",
            json=payment_data,
            headers=auth_header(owner_token),
        )
        payment_id = create_response.json()["id"]

        # Verify invoice is partial
        invoice_response = await client.get(
            f"/api/v1/invoices/{invoice.id}",
            headers=auth_header(owner_token),
        )
        assert invoice_response.json()["status"] == "partial"

        # Delete the payment
        await client.delete(
            f"/api/v1/payments/{payment_id}",
            headers=auth_header(owner_token),
        )

        # Verify invoice is back to pending
        invoice_response = await client.get(
            f"/api/v1/invoices/{invoice.id}",
            headers=auth_header(owner_token),
        )
        assert invoice_response.json()["status"] == "pending"

    async def test_delete_payment_not_found(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner_token: str,
    ):
        """Test deleting non-existent payment."""
        response = await client.delete(
            f"/api/v1/payments/{uuid4()}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 404


class TestPaymentSummary:
    """Tests for payment summary endpoint."""

    async def test_get_summary(
        self,
        client: AsyncClient,
        db: AsyncSession,
        school: School,
        payment: Payment,
        owner_token: str,
    ):
        """Test getting payment summary."""
        response = await client.get(
            f"/api/v1/payments/summary?school_id={school.id}",
            headers=auth_header(owner_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_payments"] == 1
        assert Decimal(data["total_amount"]) == Decimal("500000.00")
        assert "cash" in data["by_method"]


class TestSQLInjection:
    """Tests for SQL injection prevention."""

    async def test_create_payment_sql_injection(
        self,
        client: AsyncClient,
        db: AsyncSession,
        invoice: Invoice,
        owner_token: str,
    ):
        """Test SQL injection in note field."""
        payment_data = {
            "invoice_id": str(invoice.id),
            "amount": "100000.00",
            "payment_method": "cash",
            "note": "'; DROP TABLE payments; --",
        }

        response = await client.post(
            "/api/v1/payments",
            json=payment_data,
            headers=auth_header(owner_token),
        )
        # Should succeed but not execute the injection
        assert response.status_code == 201
        assert response.json()["note"] == "'; DROP TABLE payments; --"
