"""Student schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.validators import PhoneNumber


class StudentCreate(BaseModel):
    """Schema for creating a new student."""

    school_id: UUID
    school_class_id: UUID | None = None
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: PhoneNumber | None = None
    
    # Parent information
    parent_first_name: str = Field(..., min_length=1, max_length=100)
    parent_last_name: str = Field(..., min_length=1, max_length=100)
    parent_phone_1: PhoneNumber  # Required
    parent_phone_2: PhoneNumber | None = None
    
    monthly_fee: Decimal = Field(..., gt=0, decimal_places=2)
    payment_day: int = Field(default=5, ge=1, le=28)
    enrolled_at: date


class StudentUpdate(BaseModel):
    """Schema for updating a student."""

    school_class_id: UUID | None = None
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    phone: PhoneNumber | None = None
    
    # Parent information
    parent_first_name: str | None = Field(None, min_length=1, max_length=100)
    parent_last_name: str | None = Field(None, min_length=1, max_length=100)
    parent_phone_1: PhoneNumber | None = None
    parent_phone_2: PhoneNumber | None = None
    
    monthly_fee: Decimal | None = Field(None, gt=0, decimal_places=2)
    payment_day: int | None = Field(None, ge=1, le=28)
    graduated_at: date | None = None
    is_active: bool | None = None


class StudentResponse(BaseModel):
    """Student response schema."""

    id: UUID
    school_id: UUID
    school_class_id: UUID | None
    first_name: str
    last_name: str
    phone: str | None
    
    # Parent information
    parent_first_name: str
    parent_last_name: str
    parent_phone_1: str
    parent_phone_2: str | None
    
    monthly_fee: Decimal
    payment_day: int
    enrolled_at: date
    graduated_at: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def parent_full_name(self) -> str:
        return f"{self.parent_first_name} {self.parent_last_name}"


class StudentListResponse(BaseModel):
    """Paginated list of students."""

    items: list[StudentResponse]
    total: int
    skip: int
    limit: int
