#!/usr/bin/env python3
"""
Script to create an initial admin user for the chatbot application.

Usage:
    python scripts/create_admin_user.py
"""

import asyncio
import getpass
import sys
import os

# Add parent directory to path to import fastapi_app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi_app.postgres_models import User
from fastapi_app.auth_utils import get_password_hash
from fastapi_app.postgres_engine import create_postgres_engine_from_env
from fastapi_app.dependencies import get_azure_credential, create_async_sessionmaker
from sqlalchemy import select
from dotenv import load_dotenv


async def create_admin_user() -> None:
    """Create an admin user interactively."""

    # Load environment variables
    load_dotenv()

    print("=" * 60)
    print("Create Admin User for RAG Chatbot")
    print("=" * 60)
    print()

    # Get user input
    email = input("Email address: ").strip()
    if not email or "@" not in email:
        print("Error: Invalid email address")
        return

    username = input("Username: ").strip()
    if not username or len(username) < 3:
        print("Error: Username must be at least 3 characters")
        return

    full_name = input("Full name (optional): ").strip() or None

    # Get password with confirmation
    while True:
        password = getpass.getpass("Password (min 8 chars): ")
        if len(password) < 8:
            print("Error: Password must be at least 8 characters")
            continue

        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Error: Passwords do not match")
            continue

        break

    is_superuser_input = input("Make superuser? (y/N): ").strip().lower()
    is_superuser = is_superuser_input in ("y", "yes")

    print()
    print("Creating user...")

    try:
        # Create database connection
        azure_credential = await get_azure_credential()
        engine = await create_postgres_engine_from_env(azure_credential)
        sessionmaker = await create_async_sessionmaker(engine)

        async with sessionmaker() as session:
            # Check if user already exists
            result = await session.execute(
                select(User).where((User.email == email) | (User.username == username))
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print()
                print("❌ Error: User with this email or username already exists")
                if existing_user.email == email:
                    print(f"   Email '{email}' is already registered")
                if existing_user.username == username:
                    print(f"   Username '{username}' is already taken")
                return

            # Create new user
            hashed_password = get_password_hash(password)
            new_user = User(
                email=email,
                username=username,
                full_name=full_name,
                hashed_password=hashed_password,
                is_active=True,
                is_superuser=is_superuser,
            )

            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)

            print()
            print("✅ User created successfully!")
            print()
            print("User Details:")
            print(f"  ID:          {new_user.id}")
            print(f"  Email:       {new_user.email}")
            print(f"  Username:    {new_user.username}")
            print(f"  Full Name:   {new_user.full_name or '(not set)'}")
            print(f"  Superuser:   {new_user.is_superuser}")
            print(f"  Active:      {new_user.is_active}")
            print()
            print("You can now login with these credentials:")
            print(f"  POST /auth/login")
            print(f"  {{'username': '{username}', 'password': '***'}}")

        await engine.dispose()

    except Exception as e:
        print()
        print(f"❌ Error creating user: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(create_admin_user())
