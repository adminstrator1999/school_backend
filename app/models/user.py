"""User model."""

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.core.permissions import Role


class User(BaseModel):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    phone_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[Role] = mapped_column(
        String(20),
        nullable=False,
        default=Role.STAFF,
    )
    school_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=True,  # NULL for superusers/owner
    )
    profile_picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )

    # Relationships
    school: Mapped["School | None"] = relationship("School", back_populates="users")
    received_payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="received_by"
    )
    created_expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="created_by"
    )

    @property
    def full_name(self) -> str:
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_superuser(self) -> bool:
        """Check if user is a superuser or owner."""
        return self.role in (Role.SUPERUSER, Role.OWNER)

    @property
    def is_owner(self) -> bool:
        """Check if user is the platform owner."""
        return self.role == Role.OWNER

    def __repr__(self) -> str:
        return f"<User(id={self.id}, phone={self.phone_number}, role={self.role})>"
