"""SchoolClass model."""

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel


class SchoolClass(BaseModel):
    """SchoolClass model for organizing students by grade and section."""

    __tablename__ = "school_classes"
    __table_args__ = (
        UniqueConstraint("school_id", "grade", "section", name="uq_school_grade_section"),
    )

    school_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    homeroom_teacher_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    grade: Mapped[int] = mapped_column(nullable=False)  # 1-11
    section: Mapped[str] = mapped_column(String(10), nullable=False)  # A, B, C, etc.
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="classes")
    homeroom_teacher: Mapped["Employee | None"] = relationship(
        "Employee", back_populates="homeroom_classes"
    )
    students: Mapped[list["Student"]] = relationship("Student", back_populates="school_class")

    @property
    def name(self) -> str:
        """Return class name like '1st A', '2nd B', etc."""
        suffixes = {1: "st", 2: "nd", 3: "rd"}
        suffix = suffixes.get(self.grade if self.grade < 4 else 0, "th")
        return f"{self.grade}{suffix} {self.section}"


from app.models.school import School
from app.models.student import Student
from app.models.expense import Employee
