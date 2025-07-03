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



def setup_flask_migrate():
    """Set up and run Flask-Migrate operations."""
    os.environ['FLASK_APP'] = 'app.py'
    logger.info("Starting Flask-Migrate setup for Render deployment...")

    from traffic_app import create_app
    from traffic_app.extensions import db

    app = create_app()
    with app.app_context():
        logger.info("Creating all database tables...")
        db.create_all()
        logger.info("Database tables created.")

    if not os.path.exists('migrations'):
        logger.info("Migrations directory not found. Initializing...")
        run_command('flask db init', 'Initialize Flask-Migrate')
        run_command('flask db migrate -m "Initial migration."', 'Create initial migration')
    
    logger.info("Stamping the database with the latest migration.")
    run_command('flask db stamp head', 'Stamp database')

    logger.info("Running database migrations...")
    run_command('flask db migrate -m "Auto-detecting changes"', 'Auto-detect migrations')
    run_command('flask db upgrade', 'Apply database migrations')

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