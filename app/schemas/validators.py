"""Custom validators and types."""

import re
from typing import Annotated

from pydantic import AfterValidator, Field

# Uzbekistan phone number pattern
# +998 XX YYYYYYY - country code + 2 digit operator + 7 digit number
# Allows optional spaces/dashes
PHONE_PATTERN = re.compile(r"^\+998\s?[0-9]{2}\s?[0-9]{3}\s?[0-9]{2}\s?[0-9]{2}$")


def validate_phone_number(value: str) -> str:
    """
    Validate and normalize Uzbekistan phone number.
    
    Accepts formats:
    - +998901234567
    - +998 90 1234567
    - +998 90 123 45 67
    - +998-90-123-45-67
    
    Returns normalized format: +998901234567
    """
    # Remove spaces, dashes, parentheses
    normalized = re.sub(r"[\s\-\(\)]", "", value)
    
    # Check if it matches the pattern (without spaces)
    if not re.match(r"^\+998[0-9]{9}$", normalized):
        raise ValueError(
            "Invalid phone number. Use format: +998 XX YYYYYYY (e.g., +998 90 1234567)"
        )
    
    return normalized


# Annotated type for phone number validation
PhoneNumber = Annotated[
    str,
    Field(min_length=9, max_length=20),
    AfterValidator(validate_phone_number),
]
