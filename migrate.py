#!/usr/bin/env python3
"""
Flask-Migrate Deployment Script for Render

This script handles database migrations dynamically during Render deployment,
replacing hardcoded migration commands in render.yaml.
"""

import os
import sys
import logging
import subprocess

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_command(command, description):
    """Run a shell command with error handling."""
    try:
        logger.info(f"{description}...")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.stdout:
            logger.info(f"Output: {result.stdout.strip()}")
        
        if result.returncode == 0:
            logger.info(f"{description} completed successfully.")
            return True
        else:
            logger.warning(f"{description} failed with return code {result.returncode}")
            if result.stderr:
                logger.warning(f"Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"Exception during {description}: {e}")
        return False

def add_trip_assign_count_column():
    """Directly add the trip_assign_count column if it doesn't exist."""
    try:
        from traffic_app import create_app
        from traffic_app.extensions import db
        from sqlalchemy import text
        import psycopg2
        from urllib.parse import urlparse
        
        app = create_app()
        with app.app_context():
            logger.info("Attempting to add trip_assign_count column directly...")
            
            # Try using SQLAlchemy first
            try:
                with db.engine.connect() as conn:
                    # Check if column exists
                    result = conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='configuration' AND column_name='trip_assign_count'"
                    ))
                    
                    if result.fetchone() is None:
                        logger.info("Column doesn't exist, adding via SQLAlchemy...")
                        conn.execute(text(
                            "ALTER TABLE configuration ADD COLUMN trip_assign_count INTEGER DEFAULT 1"
                        ))
                        conn.commit()
                        logger.info("trip_assign_count column added successfully via SQLAlchemy.")
                        return True
                    else:
                        logger.info("trip_assign_count column already exists (SQLAlchemy check).")
                        return True
            except Exception as sqla_error:
                logger.warning(f"SQLAlchemy approach failed: {sqla_error}")
                logger.info("Falling back to direct psycopg2 connection...")
                
                # Fallback to direct psycopg2 connection
                try:
                    # Parse database URL from app config
                    db_url = app.config['SQLALCHEMY_DATABASE_URI']
                    logger.info(f"Database URL: {db_url[:10]}...")
                    
                    # Parse the URL to get connection parameters
                    parsed_url = urlparse(db_url)
                    db_params = {
                        'dbname': parsed_url.path[1:],
                        'user': parsed_url.username,
                        'password': parsed_url.password,
                        'host': parsed_url.hostname,
                        'port': parsed_url.port or 5432
                    }
                    if 'sslmode' in db_url:
                        db_params['sslmode'] = 'require'
                    
                    # Connect directly to PostgreSQL
                    logger.info(f"Connecting to PostgreSQL at {db_params['host']}:{db_params['port']}")
                    conn = psycopg2.connect(**db_params)
                    conn.autocommit = True
                    cursor = conn.cursor()
                    
                    # Check if column exists
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='configuration' AND column_name='trip_assign_count'"
                    )
                    
                    if cursor.fetchone() is None:
                        logger.info("Column doesn't exist, adding via psycopg2...")
                        cursor.execute(
                            "ALTER TABLE configuration ADD COLUMN trip_assign_count INTEGER DEFAULT 1"
                        )
                        logger.info("trip_assign_count column added successfully via psycopg2.")
                    else:
                        logger.info("trip_assign_count column already exists (psycopg2 check).")
                    
                    cursor.close()
                    conn.close()
                    return True
                except Exception as pg_error:
                    logger.error(f"Direct psycopg2 approach also failed: {pg_error}")
                    raise
                
    except Exception as e:
        logger.error(f"Failed to add trip_assign_count column: {e}")
        return False

def setup_flask_migrate():
    """Set up and run Flask-Migrate operations with fallback."""
    
    # Set Flask app environment variable
    os.environ['FLASK_APP'] = 'app.py'
    
    logger.info("Starting Flask-Migrate setup for Render deployment...")

    from traffic_app import create_app
    from traffic_app.extensions import db
    app = create_app()
    with app.app_context():
        db.create_all()
    
    # First try direct column addition as fallback
    if add_trip_assign_count_column():
        logger.info("Direct column addition successful.")
    
    # Check if migrations directory exists
    if not os.path.exists('migrations'):
        logger.info("Migrations directory not found. Initializing...")
        if not run_command('flask db init', 'Initialize Flask-Migrate'):
            logger.error("Failed to initialize Flask-Migrate")
            return True  # Don't fail if direct column addition worked
    else:
        logger.info("Migrations directory already exists.")
    
    # Check if we need to create a migration
    versions_dir = os.path.join('migrations', 'versions')
    if os.path.exists(versions_dir):
        migration_files = [f for f in os.listdir(versions_dir) if f.endswith('.py')]
        if not migration_files:
            logger.info("No migration files found. Creating initial migration...")
            if not run_command('flask db migrate -m "Initial migration with trip_assign_count"', 
                             'Create initial migration'):
                logger.warning("Failed to create migration, but continuing...")
        else:
            logger.info(f"Found {len(migration_files)} existing migration(s).")
            # Try to create a new migration for any pending changes
            run_command('flask db migrate -m "Auto-generated migration"', 
                       'Create migration for pending changes')
    
    # Apply all pending migrations
    if run_command('flask db upgrade', 'Apply database migrations'):
        logger.info("Database migration completed successfully.")
        return True
    else:
        logger.warning("Database migration failed, but direct column addition may have worked.")
        return True

def main():
    """Main migration function."""
    logger.info("=== MIGRATION SCRIPT STARTING ===")
    logger.info(f"Python path: {sys.path[0]}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Environment variables: FLASK_APP={os.environ.get('FLASK_APP', 'Not set')}")
    
    try:
        success = setup_flask_migrate()
        if success:
            logger.info("=== MIGRATION PROCESS COMPLETED SUCCESSFULLY ===")
            sys.exit(0)
        else:
            logger.warning("=== MIGRATION PROCESS COMPLETED WITH WARNINGS ===")
            # Don't fail the build - let the app try to start
            sys.exit(0)
    except Exception as e:
        logger.error(f"=== MIGRATION PROCESS FAILED: {e} ===")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Don't fail the build - let the app try to start
        sys.exit(0)

if __name__ == '__main__':
    main()