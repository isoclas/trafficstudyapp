# --- START OF traffic_app/__init__.py ---
import os
import logging
from datetime import datetime
from flask import Flask

# Import extensions and models AFTER defining create_app to avoid circular imports
# if extensions/models need the app context during import time (less common now).
# It's generally safer to import them inside create_app or after db.init_app()

def create_app(config_name=None):
    """Creates and configures the Flask application."""
    app = Flask(__name__, instance_relative_config=True, template_folder='../templates', static_folder='../static', static_url_path='/static')

    # 1. Load Configuration
    from .config import config
    
    # Determine configuration to use
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    
    config_class = config.get(config_name, config['default'])
    app.config.from_object(config_class)
    app.config.from_pyfile('config.py', silent=True)

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
    
    # Import models so SQLAlchemy knows about them
    from . import models
    
    # Create database tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created successfully")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {e}")
    
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

# --- END OF traffic_app/__init__.py ---