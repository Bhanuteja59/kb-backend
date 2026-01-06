import sys
import os
from sqlalchemy import create_engine, text

# Add current dir to path to find app module if needed, 
# though we just need the DB URL.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

def migrate():
    print(f"Connecting to DB: {settings.database_url}")
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        
        # 1. Add 'plan' to 'organization'
        print("Checking 'organization' table for 'plan' column...")
        try:
            conn.execute(text("ALTER TABLE organization ADD COLUMN plan VARCHAR DEFAULT 'free'"))
            # Update existing records to 'free' just in case default didn't catch (though it should)
            conn.execute(text("UPDATE organization SET plan = 'free' WHERE plan IS NULL"))
            print(" -> Added 'plan' column.")
        except Exception as e:
            if "already exists" in str(e):
                print(" -> 'plan' column already exists.")
            else:
                print(f"Error adding plan column: {e}")

        # 2. Add 'source_id' to 'document'
        print("Checking 'document' table for 'source_id' column...")
        try:
            conn.execute(text("ALTER TABLE document ADD COLUMN source_id VARCHAR"))
            print(" -> Added 'source_id' column.")
        except Exception as e:
            if "already exists" in str(e):
                print(" -> 'source_id' column already exists.")
            else:
                print(f"Error adding source_id column: {e}")
                
        # 3. Create indices if possible (Postgres specific syntax usually, generic SQL might accept it)
        # We'll skip complex index creation via raw SQL to avoid dialect issues, 
        # relying on the fact that performance won't be killed immediately.
        # But let's try a simple one.
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organization_plan ON organization (plan)"))
            print(" -> Created index on organization.plan")
        except Exception as e:
            print(f"Index creation note: {e}")

        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_source_id ON document (source_id)"))
            print(" -> Created index on document.source_id")
        except Exception as e:
            print(f"Index creation note: {e}")

    print("Migration complete.")

if __name__ == "__main__":
    migrate()
