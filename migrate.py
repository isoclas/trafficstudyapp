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
        
        app = create_app()
        
        with app.app_context():
            # First ensure all tables exist
            logger.info("Ensuring all tables exist...")
            db.create_all()
            
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            logger.info(f"Available tables: {table_names}")
            
            # Fix known issue with trip_assign_count column
            if 'configuration' in table_names:
                existing_columns = [col['name'] for col in inspector.get_columns('configuration')]
                logger.info(f"Existing columns in configuration table: {existing_columns}")
                
                if 'trip_assign_count' not in existing_columns:
                    logger.info("Adding missing trip_assign_count column...")
                    
                    try:
                        # Add the missing column with proper error handling
                        add_column_sql = """
                        ALTER TABLE configuration 
                        ADD COLUMN trip_assign_count INTEGER DEFAULT 1 NOT NULL;
                        """
                        
                        db.session.execute(text(add_column_sql))
                        db.session.commit()
                        
                        logger.info("Successfully added trip_assign_count column.")
                        
                        # Verify the column was added
                        inspector = inspect(db.engine)
                        updated_columns = [col['name'] for col in inspector.get_columns('configuration')]
                        if 'trip_assign_count' in updated_columns:
                            logger.info("Column addition verified successfully.")
                        else:
                            logger.error("Column addition verification failed.")
                            
                    except Exception as col_error:
                        logger.error(f"Failed to add trip_assign_count column: {col_error}")
                        # Try alternative approach
                        try:
                            logger.info("Trying alternative column addition approach...")
                            db.session.rollback()
                            
                            # Check if column exists using a different method
                            check_sql = """
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'configuration' 
                            AND column_name = 'trip_assign_count';
                            """
                            result = db.session.execute(text(check_sql)).fetchone()
                            
                            if not result:
                                db.session.execute(text(add_column_sql))
                                db.session.commit()
                                logger.info("Successfully added column using alternative method.")
                            else:
                                logger.info("Column already exists (detected via information_schema).")
                                
                        except Exception as alt_error:
                            logger.error(f"Alternative column addition also failed: {alt_error}")
                            db.session.rollback()
                else:
                    logger.info("Column trip_assign_count already exists.")
            else:
                logger.warning("Configuration table not found. This might be a new database.")
            
            # Fix missing order_index column in scenario table
            if 'scenario' in table_names:
                existing_columns = [col['name'] for col in inspector.get_columns('scenario')]
                logger.info(f"Existing columns in scenario table: {existing_columns}")
                
                if 'order_index' not in existing_columns:
                    logger.info("Adding missing order_index column...")
                    
                    try:
                        # Add the missing column with proper error handling
                        add_column_sql = """
                        ALTER TABLE scenario 
                        ADD COLUMN order_index INTEGER DEFAULT 0 NOT NULL;
                        """
                        
                        db.session.execute(text(add_column_sql))
                        db.session.commit()
                        
                        logger.info("Successfully added order_index column.")
                        
                        # Verify the column was added
                        inspector = inspect(db.engine)
                        updated_columns = [col['name'] for col in inspector.get_columns('scenario')]
                        if 'order_index' in updated_columns:
                            logger.info("order_index column addition verified successfully.")
                        else:
                            logger.error("order_index column addition verification failed.")
                            
                    except Exception as col_error:
                        logger.error(f"Failed to add order_index column: {col_error}")
                        db.session.rollback()
                else:
                    logger.info("Column order_index already exists.")
            else:
                logger.warning("Scenario table not found. This might be a new database.")
            
            return True
            
    except Exception as e:
        logger.error(f"Column fix failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
            sys.exit(0)
    except Exception as e:
        logger.error(f"=== MIGRATION PROCESS FAILED: {e} ===")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(0)

if __name__ == '__main__':
    main()