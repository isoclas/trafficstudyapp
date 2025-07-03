import os
import logging
from datetime import datetime
from flask import Flask

def _ensure_database_schema(app, db):
    """Ensure database schema matches the models, fixing any missing columns."""
    try:
        from sqlalchemy import text, inspect
        
        inspector = inspect(db.engine)
        
        # Check configuration table for missing trip_assign_count column
        if 'configuration' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('configuration')]
            
            if 'trip_assign_count' not in existing_columns:
                app.logger.info("Adding missing trip_assign_count column to configuration table...")
                
                try:
                    add_column_sql = """
                    ALTER TABLE configuration 
                    ADD COLUMN trip_assign_count INTEGER DEFAULT 1 NOT NULL;
                    """
                    
                    db.session.execute(text(add_column_sql))
                    db.session.commit()
                    
                    app.logger.info("Successfully added trip_assign_count column during app startup.")
                    
                except Exception as col_error:
                    app.logger.warning(f"Failed to add trip_assign_count column: {col_error}")
                    db.session.rollback()
                    
                    # Try alternative check
                    try:
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
                            app.logger.info("Successfully added column using alternative method.")
                        else:
                            app.logger.info("Column already exists (detected via information_schema).")
                            
                    except Exception as alt_error:
                        app.logger.error(f"All attempts to add trip_assign_count column failed: {alt_error}")
                        db.session.rollback()
            else:
                app.logger.info("trip_assign_count column already exists in configuration table.")
        else:
            app.logger.warning("Configuration table not found during schema check.")
            
    except Exception as e:
        app.logger.error(f"Database schema check failed: {e}")
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")

def create_app(config_name=None):
    """Creates and configures the Flask application."""
    app = Flask(
        __name__, 
        instance_relative_config=True, 
        template_folder='../templates', 
        static_folder='../static', 
        static_url_path='/static'
    )

    # 1. Load Configuration
    from .config import config
    
    # Determine configuration to use
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    
    config_class = config.get(config_name, config['default'])
    app.config.from_object(config_class)
    app.config.from_pyfile('config.py', silent=True)
    
    # Set the database URI using the classmethod
    db_uri = config_class.get_database_uri()
    if 'sslmode' in db_uri:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {'sslmode': 'require'}
        }
        # Remove sslmode from the URI as it's now in connect_args
        db_uri = db_uri.split('?')[0]
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    
    # Initialize configuration-specific settings
    if hasattr(config_class, 'init_app'):
        config_class.init_app(app)

    # Ensure BASE_DIR is correctly set in config if not already derived properly
    if 'BASE_DIR' not in app.config:
         app.config['BASE_DIR'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # 2. Configure Logging
    logging.basicConfig(
        level=app.config.get('LOGGING_LEVEL', 'INFO'),
        format=app.config.get('LOGGING_FORMAT', '%(asctime)s - %(levelname)s - %(message)s')
    )
    app.logger.info("Flask App Initializing...")

    # 3. Create Essential Directories (only for local storage)
    if not app.config.get('USE_CLOUDINARY'):
        os.makedirs(os.path.join(app.config['BASE_DIR'], "instance"), exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
        app.logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
        app.logger.info(f"Output folder: {app.config['OUTPUT_FOLDER']}")

    # 4. Initialize Extensions
    from .extensions import db
    db.init_app(app)
    app.logger.info("Database Initialized.")
    
    # Initialize Flask-Migrate
    from flask_migrate import Migrate
    migrate = Migrate(app, db)
    app.logger.info("Flask-Migrate Initialized.")
    
    # Import models so SQLAlchemy knows about them
    from . import models
    
    # Ensure database schema is up to date
    with app.app_context():
        try:
            # Always create tables first (safe operation)
            db.create_all()
            app.logger.info("Database tables ensured")
            
            # Check and fix missing columns
            _ensure_database_schema(app, db)
            
        except Exception as e:
            app.logger.error(f"Error ensuring database schema: {e}")
            if app.config.get('TESTING'):
                raise  # Re-raise in testing to fail fast
    
    # 5. Initialize Cloudinary
    with app.app_context():
        from .storage import init_cloudinary
        init_cloudinary()

    # 6. Import and Register Blueprints
    from .routes.api import api_bp
    from .routes.frontend import frontend_bp
    
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(frontend_bp)
    
    # 7. Register Error Handlers
    from .error_handlers import register_error_handlers
    register_error_handlers(app)
    
    app.logger.info("Flask App Initialization Complete.")
    return app