"""Employee schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.validators import PhoneNumber


class PositionInfo(BaseModel):
    """Nested position info for employee response."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}


class EmployeeCreate(BaseModel):
    """Schema for creating a new employee."""

    school_id: UUID
    position_id: UUID
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: PhoneNumber | None = None
    profile_picture: str | None = Field(None, max_length=500)
    salary: Decimal = Field(..., gt=0, decimal_places=2)


class EmployeeUpdate(BaseModel):
    """Schema for updating an employee."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    phone: PhoneNumber | None = None
    profile_picture: str | None = Field(None, max_length=500)
    position_id: UUID | None = None
    salary: Decimal | None = Field(None, gt=0, decimal_places=2)
    is_active: bool | None = None


class EmployeeResponse(BaseModel):
    """Employee response schema."""

    id: UUID
    school_id: UUID
    position_id: UUID
    position: PositionInfo
    first_name: str
    last_name: str
    full_name: str
    phone: str | None
    profile_picture: str | None
    salary: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    """Paginated list of employees."""

    items: list[EmployeeResponse]
    total: int
    skip: int
    limit: int
