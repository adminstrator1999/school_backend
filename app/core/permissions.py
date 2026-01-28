"""User roles and permissions."""

from enum import Enum


class Role(str, Enum):
    """User roles in the system."""

    OWNER = "owner"  # Platform owner, can create superusers
    SUPERUSER = "superuser"  # Platform admin, access to all schools
    DIRECTOR = "director"  # Full access to their school
    SHAREHOLDER = "shareholder"  # Same as director (school owner/investor)
    ACCOUNTANT = "accountant"  # Financial operations in their school
    STAFF = "staff"  # Limited access in their school


# Permissions by role
ROLE_PERMISSIONS = {
    Role.OWNER: [
        "schools:read",
        "schools:write",
        "users:read",
        "users:write",
        "users:create_superuser",  # Only owner can create superusers
        "students:read",
        "students:write",
        "payments:read",
        "payments:write",
        "expenses:read",
        "expenses:write",
        "reports:read",
    ],
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


# Which roles can create which other roles
ROLE_HIERARCHY = {
    Role.OWNER: [Role.SUPERUSER, Role.DIRECTOR, Role.SHAREHOLDER, Role.ACCOUNTANT, Role.STAFF],
    Role.SUPERUSER: [Role.DIRECTOR, Role.SHAREHOLDER, Role.ACCOUNTANT, Role.STAFF],
    Role.DIRECTOR: [Role.ACCOUNTANT, Role.STAFF],
    Role.SHAREHOLDER: [Role.DIRECTOR, Role.ACCOUNTANT, Role.STAFF],
    Role.ACCOUNTANT: [],
    Role.STAFF: [],
}


def has_permission(role: Role, permission: str) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, [])


def can_create_role(creator_role: Role, target_role: Role) -> bool:
    """Check if a role can create another role."""
    return target_role in ROLE_HIERARCHY.get(creator_role, [])


def can_manage_schools(role: Role) -> bool:
    """Check if role can create/manage schools."""
    return role in (Role.OWNER, Role.SUPERUSER)
