"""Discount schemas."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.discount import DiscountType


class DiscountCreate(BaseModel):
    """Schema for creating a discount."""

    school_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    type: DiscountType
    value: Decimal = Field(..., gt=0)
    valid_from: date | None = None
    valid_until: date | None = None

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Decimal, info) -> Decimal:
        """Validate value based on discount type."""
        # For percentage, value should be <= 100
        if info.data.get("type") == DiscountType.PERCENTAGE and v > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        return v


class DiscountUpdate(BaseModel):
    """Schema for updating a discount."""

    name: str | None = Field(None, min_length=1, max_length=100)
    type: DiscountType | None = None
    value: Decimal | None = Field(None, gt=0)
    valid_from: date | None = None
    valid_until: date | None = None
    is_active: bool | None = None


class DiscountResponse(BaseModel):
    """Discount response schema."""

    id: UUID
    school_id: UUID
    name: str
    type: DiscountType
    value: Decimal
    valid_from: date | None
    valid_until: date | None
    is_active: bool

    model_config = {"from_attributes": True}


class DiscountListResponse(BaseModel):
    """Paginated list of discounts."""

    items: list[DiscountResponse]
    total: int


# ============== Student Discount Schemas ==============


class StudentDiscountCreate(BaseModel):
    """Schema for assigning a discount to a student."""

    student_id: UUID
    discount_id: UUID


class StudentDiscountResponse(BaseModel):
    """Student discount assignment response."""

    id: UUID
    student_id: UUID
    discount_id: UUID
    discount: DiscountResponse

    model_config = {"from_attributes": True}


class StudentDiscountsResponse(BaseModel):
    """List of discounts assigned to a student."""

    student_id: UUID
    discounts: list[DiscountResponse]
