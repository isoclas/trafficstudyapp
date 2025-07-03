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



def fix_missing_columns():
    """Automatically fix missing columns in the database."""
    logger.info("Checking for missing database columns...")
    try:
        from traffic_app import create_app
        from traffic_app.extensions import db
        from sqlalchemy import text, inspect
        from traffic_app.models import Configuration
        
        app = create_app()
        
        with app.app_context():
            inspector = inspect(db.engine)
            
            # Fix known issue with trip_assign_count column
            if 'configuration' in inspector.get_table_names():
                existing_columns = [col['name'] for col in inspector.get_columns('configuration')]
                
                if 'trip_assign_count' not in existing_columns:
                    logger.info("Adding missing trip_assign_count column...")
                    
                    # Add the missing column
                    add_column_sql = """
                    ALTER TABLE configuration 
                    ADD COLUMN trip_assign_count INTEGER DEFAULT 1 NOT NULL;
                    """
                    
                    db.session.execute(text(add_column_sql))
                    db.session.commit()
                    
                    logger.info("Successfully added trip_assign_count column.")
                else:
                    logger.info("Column trip_assign_count already exists.")
            
            # Check for any other missing columns in Configuration table
            # This is a more general approach that could be expanded to other models
            logger.info("Checking for other missing columns in Configuration table...")
            
            # Get all model columns
            model_columns = Configuration.__table__.columns.keys()
            
            # Get existing database columns
            if 'configuration' in inspector.get_table_names():
                existing_columns = [col['name'] for col in inspector.get_columns('configuration')]
                
                # Find missing columns
                missing_columns = set(model_columns) - set(existing_columns)
                
                if missing_columns:
                    logger.info(f"Found additional missing columns: {missing_columns}")
                    # Here you could add code to automatically add these columns
                    # For now, we'll just log them so they can be handled by Flask-Migrate
                else:
                    logger.info("No additional missing columns found.")
            
            return True
            
    except Exception as e:
        logger.warning(f"Column fix failed: {e}")
        import traceback
        logger.warning(f"Traceback: {traceback.format_exc()}")
        return False

def setup_flask_migrate():
    """Set up and run Flask-Migrate operations."""
    os.environ['FLASK_APP'] = 'app.py'
    logger.info("Starting Flask-Migrate setup for Render deployment...")

    from traffic_app import create_app
    from traffic_app.extensions import db

    app = create_app()
    
    # First, try to fix any missing columns
    fix_missing_columns()
    
    if not os.path.exists('migrations'):
        logger.info("Migrations directory not found. Initializing...")
        with app.app_context():
            # First create all tables for initial setup
            logger.info("Creating all database tables for initial setup...")
            db.create_all()
            logger.info("Database tables created.")
        
        run_command('flask db init', 'Initialize Flask-Migrate')
        run_command('flask db stamp head', 'Stamp database as current')
    else:
        logger.info("Migrations directory found. Running migrations...")
        run_command('flask db migrate -m "Auto-detecting schema changes"', 'Auto-detect migrations')
        run_command('flask db upgrade', 'Apply database migrations')
    
    # Always try to detect and apply any new changes
    logger.info("Checking for additional schema changes...")
    run_command('flask db migrate -m "Add missing columns"', 'Detect missing columns')
    run_command('flask db upgrade', 'Apply any pending migrations')

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