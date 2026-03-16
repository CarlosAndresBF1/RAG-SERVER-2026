import asyncio
import os
import sys

# Ensure src is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import bcrypt
from sqlalchemy import text
from odyssey_rag.db.session import db_session

async def main():
    email = os.getenv("ADMIN_EMAIL", "admin@odyssey.local")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    display_name = "Admin User"

    print(f"Seeding admin user: {email}")

    # Hash password
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    query = text("""
        INSERT INTO admin_user (email, password_hash, display_name, role)
        VALUES (:email, :password_hash, :display_name, 'admin')
        ON CONFLICT (email) DO UPDATE 
        SET password_hash = EXCLUDED.password_hash,
            updated_at = NOW()
    """)

    try:
        async with db_session() as session:
            await session.execute(
                query, 
                {
                    "email": email,
                    "password_hash": password_hash,
                    "display_name": display_name
                }
            )
        print("Admin user seeded successfully.")
    except Exception as e:
        print(f"Error seeding admin user: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
