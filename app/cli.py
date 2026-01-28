"""CLI commands for management tasks."""

import asyncio
import sys

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.permissions import Role
from app.core.security import get_password_hash
from app.models.user import User


async def create_owner(
    phone_number: str,
    password: str,
    first_name: str,
    last_name: str,
) -> None:
    """Create the initial owner user."""
    async with async_session_maker() as db:
        # Check if any owner exists
        result = await db.execute(
            select(User).where(User.role == Role.OWNER)
        )
        existing_owner = result.scalar_one_or_none()
        
        if existing_owner:
            print("Error: An owner already exists!")
            print(f"Owner: {existing_owner.full_name} ({existing_owner.phone_number})")
            sys.exit(1)
        
        # Check if phone number is taken
        result = await db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        if result.scalar_one_or_none():
            print(f"Error: Phone number {phone_number} is already registered!")
            sys.exit(1)
        
        # Create owner
        owner = User(
            phone_number=phone_number,
            password_hash=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            role=Role.OWNER,
            school_id=None,
        )
        
        db.add(owner)
        await db.commit()
        await db.refresh(owner)
        
        print(f"✓ Owner created successfully!")
        print(f"  ID: {owner.id}")
        print(f"  Name: {owner.full_name}")
        print(f"  Phone: {owner.phone_number}")


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli <command>")
        print("Commands:")
        print("  create-owner <phone> <password> <first_name> <last_name>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create-owner":
        if len(sys.argv) != 6:
            print("Usage: python -m app.cli create-owner <phone> <password> <first_name> <last_name>")
            sys.exit(1)
        
        _, _, phone, password, first_name, last_name = sys.argv
        asyncio.run(create_owner(phone, password, first_name, last_name))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
