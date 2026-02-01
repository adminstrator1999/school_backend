"""Employee service layer."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense import Employee, Position
from app.schemas.employee import EmployeeCreate, EmployeeUpdate


async def get_employee_by_id(db: AsyncSession, employee_id: UUID) -> Employee | None:
    """Get an employee by ID."""
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.position))
        .where(Employee.id == employee_id)
    )
    return result.scalar_one_or_none()


async def get_employees(
    db: AsyncSession,
    *,
    school_id: UUID | None = None,
    position_id: UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Employee], int]:
    """Get all employees with optional filters."""
    query = select(Employee).options(selectinload(Employee.position))
    count_query = select(func.count(Employee.id))

    if school_id:
        query = query.where(Employee.school_id == school_id)
        count_query = count_query.where(Employee.school_id == school_id)

    if position_id:
        query = query.where(Employee.position_id == position_id)
        count_query = count_query.where(Employee.position_id == position_id)

    if is_active is not None:
        query = query.where(Employee.is_active == is_active)
        count_query = count_query.where(Employee.is_active == is_active)

    if search:
        search_filter = (
            Employee.first_name.ilike(f"%{search}%")
            | Employee.last_name.ilike(f"%{search}%")
            | Employee.phone.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Order by name
    query = query.order_by(Employee.last_name, Employee.first_name)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    employees = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return employees, total


async def get_employees_by_school(
    db: AsyncSession,
    school_id: UUID,
    *,
    is_active: bool | None = True,
) -> list[Employee]:
    """Get all employees for a school."""
    query = (
        select(Employee)
        .options(selectinload(Employee.position))
        .where(Employee.school_id == school_id)
    )

    if is_active is not None:
        query = query.where(Employee.is_active == is_active)

    result = await db.execute(query.order_by(Employee.last_name, Employee.first_name))
    return list(result.scalars().all())


async def create_employee(db: AsyncSession, employee_data: EmployeeCreate) -> Employee:
    """Create a new employee."""
    employee = Employee(
        school_id=employee_data.school_id,
        position_id=employee_data.position_id,
        first_name=employee_data.first_name,
        last_name=employee_data.last_name,
        phone=employee_data.phone,
        profile_picture=employee_data.profile_picture,
        salary=employee_data.salary,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    # Reload with position
    return await get_employee_by_id(db, employee.id)  # type: ignore


async def update_employee(
    db: AsyncSession, employee: Employee, employee_data: EmployeeUpdate
) -> Employee:
    """Update an employee."""
    update_data = employee_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(employee, field, value)

    await db.commit()
    await db.refresh(employee)
    # Reload with position
    return await get_employee_by_id(db, employee.id)  # type: ignore


async def deactivate_employee(db: AsyncSession, employee: Employee) -> None:
    """Soft delete an employee by deactivating it."""
    employee.is_active = False
    await db.commit()
