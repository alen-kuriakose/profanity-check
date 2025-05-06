"""
Script to run database migrations.
"""
import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_migration(migration_file):
    """Run a migration file against the database."""
    settings = get_settings()
    db_config = settings.database
    
    # Check if migration file exists
    if not os.path.exists(migration_file):
        logger.error(f"Migration file not found: {migration_file}")
        return False
    
    # Read migration SQL
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            user=db_config.user,
            password=db_config.password,
            database=db_config.database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Execute migration
        with conn.cursor() as cur:
            logger.info(f"Running migration: {os.path.basename(migration_file)}")
            cur.execute(migration_sql)
            logger.info(f"Migration completed successfully: {os.path.basename(migration_file)}")
        
        conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Error running migration: {str(e)}")
        return False

if __name__ == "__main__":
    # Check if migration file is provided
    if len(sys.argv) < 2:
        logger.error("Usage: python run_migration.py <migration_file>")
        sys.exit(1)
    
    # Get migration file
    migration_file = sys.argv[1]
    
    # Run migration
    success = run_migration(migration_file)
    
    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)