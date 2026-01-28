"""Discount model."""

from datetime import date
from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel


class DiscountType(str, Enum):
    """Type of discount calculation."""

    PERCENTAGE = "percentage"  # e.g., 10% off
    FIXED = "fixed"  # e.g., 50,000 UZS off


class Discount(BaseModel):
    """Discount definitions for a school."""

    __tablename__ = "discounts"

    school_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[DiscountType] = mapped_column(String(20), nullable=False)
    value: Mapped[int] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )  # Percentage (10) or fixed amount (50000)
    
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="discounts")
    students: Mapped[list["StudentDiscount"]] = relationship(
        "StudentDiscount", back_populates="discount"
    )

    def __repr__(self) -> str:
        return f"<Discount(id={self.id}, name={self.name})>"


class StudentDiscount(BaseModel):
    """Links students to their discounts."""

    __tablename__ = "student_discounts"

    student_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    discount_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("discounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="discounts")
    discount: Mapped["Discount"] = relationship("Discount", back_populates="students")

    def __repr__(self) -> str:
        return f"<StudentDiscount(student={self.student_id}, discount={self.discount_id})>"
