"""Student service."""

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate


async def get_student_by_id(db: AsyncSession, student_id: UUID) -> Student | None:
    """Get student by ID."""
    result = await db.execute(select(Student).where(Student.id == student_id))
    return result.scalar_one_or_none()


async def get_students(
    db: AsyncSession,
    *,
    school_id: UUID | None = None,
    school_class_id: UUID | None = None,
    is_active: bool | None = None,
    graduated: bool | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Student], int]:
    """Get list of students with optional filters."""
    query = select(Student)
    count_query = select(func.count()).select_from(Student)

    # Apply filters
    if school_id is not None:
        query = query.where(Student.school_id == school_id)
        count_query = count_query.where(Student.school_id == school_id)

    if school_class_id is not None:
        query = query.where(Student.school_class_id == school_class_id)
        count_query = count_query.where(Student.school_class_id == school_class_id)

    if is_active is not None:
        query = query.where(Student.is_active == is_active)
        count_query = count_query.where(Student.is_active == is_active)

    if graduated is not None:
        if graduated:
            query = query.where(Student.graduated_at != None)
            count_query = count_query.where(Student.graduated_at != None)
        else:
            query = query.where(Student.graduated_at == None)
            count_query = count_query.where(Student.graduated_at == None)

    if search:
        search_filter = (
            Student.first_name.ilike(f"%{search}%")
            | Student.last_name.ilike(f"%{search}%")
            | Student.phone.ilike(f"%{search}%")
            | Student.parent_phone_1.ilike(f"%{search}%")
            | Student.parent_phone_2.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(Student.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    students = list(result.scalars().all())

    return students, total


async def create_student(db: AsyncSession, student_data: StudentCreate) -> Student:
    """Create a new student."""
    student = Student(
        school_id=student_data.school_id,
        school_class_id=student_data.school_class_id,
        first_name=student_data.first_name,
        last_name=student_data.last_name,
        phone=student_data.phone,
        parent_first_name=student_data.parent_first_name,
        parent_last_name=student_data.parent_last_name,
        parent_phone_1=student_data.parent_phone_1,
        parent_phone_2=student_data.parent_phone_2,
        monthly_fee=student_data.monthly_fee,
        payment_day=student_data.payment_day,
        enrolled_at=student_data.enrolled_at,
    )

    db.add(student)
    await db.commit()
    await db.refresh(student)

    return student


async def update_student(
    db: AsyncSession,
    student: Student,
    student_data: StudentUpdate,
) -> Student:
    """Update a student."""
    update_data = student_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(student, field, value)

    await db.commit()
    await db.refresh(student)

    return student


async def deactivate_student(db: AsyncSession, student: Student) -> Student:
    """Soft delete a student by setting is_active to False."""
    student.is_active = False
    await db.commit()
    await db.refresh(student)
    return student


async def get_students_by_school(
    db: AsyncSession,
    school_id: UUID,
    *,
    is_active: bool | None = True,
) -> list[Student]:
    """Get all students for a school."""
    query = select(Student).where(Student.school_id == school_id)

    if is_active is not None:
        query = query.where(Student.is_active == is_active)

    result = await db.execute(query.order_by(Student.last_name, Student.first_name))
    return list(result.scalars().all())
