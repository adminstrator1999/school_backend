"""User roles and permissions."""

from enum import Enum


class Role(str, Enum):
    """User roles in the system."""

    SUPERUSER = "superuser"  # Platform admin, access to all schools
    DIRECTOR = "director"  # Full access to their school
    SHAREHOLDER = "shareholder"  # Same as director (school owner/investor)
    ACCOUNTANT = "accountant"  # Financial operations in their school
    STAFF = "staff"  # Limited access in their school


# Permissions by role
ROLE_PERMISSIONS = {
    Role.SUPERUSER: [
        "schools:read",
        "schools:write",
        "users:read",
        "users:write",
        "students:read",
        "students:write",
        "payments:read",
        "payments:write",
        "expenses:read",
        "expenses:write",
        "reports:read",
    ],
    Role.DIRECTOR: [
        "users:read",
        "users:write",
        "students:read",
        "students:write",
        "payments:read",
        "payments:write",
        "expenses:read",
        "expenses:write",
        "reports:read",
    ],
    Role.SHAREHOLDER: [
        "users:read",
        "users:write",
        "students:read",
        "students:write",
        "payments:read",
        "payments:write",
        "expenses:read",
        "expenses:write",
        "reports:read",
    ],
    Role.ACCOUNTANT: [
        "students:read",
        "payments:read",
        "payments:write",
        "expenses:read",
        "expenses:write",
        "reports:read",
    ],
    Role.STAFF: [
        "students:read",
        "payments:read",
        "reports:read",
    ],
}


def has_permission(role: Role, permission: str) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, [])
