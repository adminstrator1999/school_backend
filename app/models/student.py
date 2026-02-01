"""Student model."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel


class Student(BaseModel):
    """Student model - source of income for schools."""

    __tablename__ = "students"

    school_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    school_class_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("school_classes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    
    # Parent information
    parent_first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_phone_1: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_phone_2: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Payment settings
    monthly_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    payment_day: Mapped[int] = mapped_column(
        Integer,
        default=5,
        server_default="5",
    )  # Day of month for payment deadline
    
    enrolled_at: Mapped[date] = mapped_column(Date, nullable=False)
    graduated_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="students")
    school_class: Mapped["SchoolClass"] = relationship("SchoolClass", back_populates="students")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="student")
    discounts: Mapped[list["StudentDiscount"]] = relationship(
        "StudentDiscount", back_populates="student"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Student(id={self.id}, name={self.full_name})>"
