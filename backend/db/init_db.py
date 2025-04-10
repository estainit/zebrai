import os
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import pdb  # Add this import
from app.core.logging import logger

# Load environment variables
load_dotenv()

# Database configuration
DB_NAME = os.getenv("ZEB_DB", "dbzebrai")
DB_USER = os.getenv("ZEB_USER", "userzebrai")
DB_PASS = os.getenv("ZEB_PASSWORD", "passzebrai")
DB_HOST = os.getenv("ZEB_HOST", "localhost")
DB_PORT = os.getenv("ZEB_PORT", "5444")

def get_db_connection(dbname=None):
    """Get a database connection."""
    try:
        print(f"DB_NAME: {DB_NAME}")
        print(f"DB_PASS: {DB_PASS}")
        conn = psycopg2.connect(
            dbname=dbname or DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT
        )
        logger.info(f"Successfully connected to database {dbname or DB_NAME}")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def init_db():
    """Initialize the database by running all migration scripts."""
    try:
        # First, connect to postgres database to create our database if it doesn't exist
        conn = get_db_connection("postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE {DB_NAME}')
            logger.info(f"Created database {DB_NAME}")
        
        cur.close()
        conn.close()
        
        # Now connect to our database and run migrations
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the migrations directory
        migrations_dir = Path(__file__).parent / "migrations"
        
        # Get all SQL files and sort them
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        # Run each migration file
        for migration_file in migration_files:
            logger.info(f"Running migration: {migration_file.name}")
            
            # Read and execute the SQL file
            with open(migration_file, 'r') as f:
                sql = f.read()
                cur.execute(sql)
            
            logger.info(f"Completed migration: {migration_file.name}")
        
        # Commit all changes
        conn.commit()
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    init_db() 