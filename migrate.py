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
    
    # Set Flask app environment variable
    os.environ['FLASK_APP'] = 'app.py'
    
    logger.info("Starting Flask-Migrate setup for Render deployment...")
    
    # Check if migrations directory exists
    if not os.path.exists('migrations'):
        logger.info("Migrations directory not found. Initializing...")
        if not run_command('flask db init', 'Initialize Flask-Migrate'):
            logger.error("Failed to initialize Flask-Migrate")
            return False
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
        logger.error("Database migration failed.")
        return False

def main():
    """Main migration function."""
    try:
        success = setup_flask_migrate()
        if success:
            logger.info("Migration process completed successfully.")
            sys.exit(0)
        else:
            logger.warning("Migration process completed with warnings.")
            # Don't fail the build - let the app try to start
            sys.exit(0)
    except Exception as e:
        logger.error(f"Migration process failed: {e}")
        # Don't fail the build - let the app try to start
        sys.exit(0)

if __name__ == '__main__':
    main()