"""Tests for phone number validator."""

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.validators import PhoneNumber, validate_phone_number


class PhoneModel(BaseModel):
    """Test model with phone number."""
    phone: PhoneNumber


class TestPhoneValidator:
    """Tests for phone number validation."""

    def test_valid_phone_compact(self):
        """Test valid phone without spaces."""
        model = PhoneModel(phone="+998901234567")
        assert model.phone == "+998901234567"

    def test_valid_phone_with_spaces(self):
        """Test valid phone with spaces."""
        model = PhoneModel(phone="+998 90 1234567")
        assert model.phone == "+998901234567"

    def test_valid_phone_with_dashes(self):
        """Test valid phone with dashes."""
        model = PhoneModel(phone="+998-90-123-45-67")
        assert model.phone == "+998901234567"

    def test_valid_phone_mixed_format(self):
        """Test valid phone with mixed separators."""
        model = PhoneModel(phone="+998 90 123 45 67")
        assert model.phone == "+998901234567"

    def test_invalid_phone_no_country_code(self):
        """Test phone without country code."""
        with pytest.raises(ValidationError) as exc_info:
            PhoneModel(phone="901234567")
        assert "Invalid phone number" in str(exc_info.value)

    def test_invalid_phone_wrong_country_code(self):
        """Test phone with wrong country code."""
        with pytest.raises(ValidationError) as exc_info:
            PhoneModel(phone="+1234567890123")
        assert "Invalid phone number" in str(exc_info.value)

    def test_invalid_phone_too_short(self):
        """Test phone number too short."""
        with pytest.raises(ValidationError) as exc_info:
            PhoneModel(phone="+99890123456")  # Missing one digit
        assert "Invalid phone number" in str(exc_info.value)

    def test_invalid_phone_too_long(self):
        """Test phone number too long."""
        with pytest.raises(ValidationError) as exc_info:
            PhoneModel(phone="+9989012345678")  # One extra digit
        assert "Invalid phone number" in str(exc_info.value)

    def test_invalid_phone_letters(self):
        """Test phone with letters."""
        with pytest.raises(ValidationError) as exc_info:
            PhoneModel(phone="+998901234abc")
        assert "Invalid phone number" in str(exc_info.value)

    def test_various_operators(self):
        """Test various Uzbek operator codes."""
        valid_phones = [
            "+998901234567",  # Beeline
            "+998911234567",  # Beeline
            "+998931234567",  # Ucell
            "+998941234567",  # Ucell
            "+998971234567",  # UzMobile
            "+998881234567",  # UMS
            "+998951234567",  # Perfectum
        ]
        
        for phone in valid_phones:
            model = PhoneModel(phone=phone)
            assert model.phone == phone
