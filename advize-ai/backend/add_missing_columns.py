import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def add_missing_columns():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'USER' AND column_name IN ('is_active', 'verification_code', 'code_expires_at');
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # Add missing columns
        if 'is_active' not in existing_columns:
            print("Adding is_active column...")
            cursor.execute('ALTER TABLE \"USER\" ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT false;')
            
        if 'verification_code' not in existing_columns:
            print("Adding verification_code column...")
            cursor.execute('ALTER TABLE \"USER\" ADD COLUMN verification_code VARCHAR;')
            
        if 'code_expires_at' not in existing_columns:
            print("Adding code_expires_at column...")
            cursor.execute('ALTER TABLE \"USER\" ADD COLUMN code_expires_at TIMESTAMP;')
        
        conn.commit()
        print("Successfully added all missing columns to USER table.")
        
    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Adding missing columns to USER table...")
    add_missing_columns()
