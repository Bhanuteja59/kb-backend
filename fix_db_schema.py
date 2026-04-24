import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import text
from app.db import engine

def fix_database():
    print("Connecting to database to fix 'role' enum issue...")
    with engine.connect() as conn:
        try:
            # 1. Drop the default on the column
            conn.execute(text('ALTER TABLE "user" ALTER COLUMN role DROP DEFAULT;'))
            print("Dropped default from role column.")
            
            # 2. Change the column type from enum to text
            conn.execute(text('ALTER TABLE "user" ALTER COLUMN role TYPE text USING role::text;'))
            print("Changed role column to text type.")
            
            # 3. Drop the old enum type from the database
            conn.execute(text('DROP TYPE IF EXISTS role CASCADE;'))
            print("Dropped old 'role' enum type.")
            
            # Commit the transaction
            conn.commit()
            print("\nSUCCESS! The database schema has been fixed.")
        except Exception as e:
            print(f"\nERROR: Could not apply schema fix: {e}")

if __name__ == "__main__":
    fix_database()
