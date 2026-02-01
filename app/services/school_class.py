"""SchoolClass service layer."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school_class import SchoolClass
from app.schemas.school_class import SchoolClassCreate, SchoolClassUpdate


async def get_school_class_by_id(
    db: AsyncSession, class_id: UUID
) -> SchoolClass | None:
    """Get a school class by ID."""
    result = await db.execute(select(SchoolClass).where(SchoolClass.id == class_id))
    return result.scalar_one_or_none()


async def get_school_classes(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    school_id: UUID | None = None,
    grade: int | None = None,
    is_active: bool | None = None,
) -> tuple[list[SchoolClass], int]:
    """Get all school classes with optional filters."""
    query = select(SchoolClass)
    count_query = select(func.count(SchoolClass.id))

    if school_id:
        query = query.where(SchoolClass.school_id == school_id)
        count_query = count_query.where(SchoolClass.school_id == school_id)

    if grade is not None:
        query = query.where(SchoolClass.grade == grade)
        count_query = count_query.where(SchoolClass.grade == grade)

    if is_active is not None:
        query = query.where(SchoolClass.is_active == is_active)
        count_query = count_query.where(SchoolClass.is_active == is_active)

    # Order by grade, then section
    query = query.order_by(SchoolClass.grade, SchoolClass.section)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    classes = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return classes, total


async def get_school_class_by_grade_section(
    db: AsyncSession, school_id: UUID, grade: int, section: str
) -> SchoolClass | None:
    """Get a school class by school, grade and section."""
    result = await db.execute(
        select(SchoolClass).where(
            SchoolClass.school_id == school_id,
            SchoolClass.grade == grade,
            SchoolClass.section == section,
        )
    )
    return result.scalar_one_or_none()


async def create_school_class(
    db: AsyncSession, class_data: SchoolClassCreate
) -> SchoolClass:
    """Create a new school class."""
    school_class = SchoolClass(
        school_id=class_data.school_id,
        homeroom_teacher_id=class_data.homeroom_teacher_id,
        grade=class_data.grade,
        section=class_data.section.upper(),  # Normalize to uppercase
    )
    db.add(school_class)
    await db.commit()
    await db.refresh(school_class)
    return school_class


async def update_school_class(
    db: AsyncSession, school_class: SchoolClass, class_data: SchoolClassUpdate
) -> SchoolClass:
    """Update a school class."""
    update_data = class_data.model_dump(exclude_unset=True)
    if "section" in update_data and update_data["section"]:
        update_data["section"] = update_data["section"].upper()
    
    for field, value in update_data.items():
        setattr(school_class, field, value)

    await db.commit()
    await db.refresh(school_class)
    return school_class


async def deactivate_school_class(db: AsyncSession, school_class: SchoolClass) -> None:
    """Soft delete a school class by deactivating it."""
    school_class.is_active = False
    await db.commit()


async def promote_students(
    db: AsyncSession, school_id: UUID
) -> dict[str, int]:
    """
    Promote all students to the next grade.
    Students in grade 11 will be graduated.
    Returns count of promoted and graduated students.
    """
    from datetime import date
    from sqlalchemy import update
    from app.models.student import Student
    
    promoted = 0
    graduated = 0
    
    # Get all active classes for this school, ordered by grade desc
    classes_result = await db.execute(
        select(SchoolClass)
        .where(SchoolClass.school_id == school_id, SchoolClass.is_active == True)
        .order_by(SchoolClass.grade.desc())
    )
    classes = list(classes_result.scalars().all())
    
    # Build a mapping of (grade, section) -> next class id
    class_map = {(c.grade, c.section): c for c in classes}
    
    for school_class in classes:
        if school_class.grade == 11:
            # Graduate students in grade 11
            result = await db.execute(
                update(Student)
                .where(
                    Student.school_class_id == school_class.id,
                    Student.is_active == True,
                    Student.graduated_at == None,
                )
                .values(graduated_at=date.today(), is_active=False)
            )
            graduated += result.rowcount
        else:
            # Find next grade class with same section
            next_class = class_map.get((school_class.grade + 1, school_class.section))
            if next_class:
                result = await db.execute(
                    update(Student)
                    .where(
                        Student.school_class_id == school_class.id,
                        Student.is_active == True,
                    )
                    .values(school_class_id=next_class.id)
                )
                promoted += result.rowcount
    
    await db.commit()
    return {"promoted": promoted, "graduated": graduated}
