# --- START OF traffic_app/__init__.py ---
import os
import logging
from datetime import datetime
from flask import Flask

# Import extensions and models AFTER defining create_app to avoid circular imports
# if extensions/models need the app context during import time (less common now).
# It's generally safer to import them inside create_app or after db.init_app()

def create_app(config_class='traffic_app.config.Config'):
    """Creates and configures the Flask application."""
    app = Flask(__name__, instance_relative_config=True, template_folder='../templates', static_folder='../static', static_url_path='/static')

    # 1. Load Configuration
    app.config.from_object(config_class)
    # Load instance config if it exists (e.g., for secrets)
    app.config.from_pyfile('config.py', silent=True)

    # Ensure BASE_DIR is correctly set in config if not already derived properly
    if 'BASE_DIR' not in app.config:
         app.config['BASE_DIR'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # 2. Configure Logging
    logging.basicConfig(
        level=app.config.get('LOGGING_LEVEL', 'INFO'),
        format=app.config.get('LOGGING_FORMAT', '%(asctime)s - %(levelname)s - %(message)s')
    )
    app.logger.info("Flask App Initializing...") # Use app.logger

    # 3. Create Essential Directories
    # Use app.config values AFTER they are loaded
    os.makedirs(os.path.join(app.config['BASE_DIR'], "instance"), exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    app.logger.info(f"Instance path: {app.instance_path}")
    app.logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    app.logger.info(f"Output folder: {app.config['OUTPUT_FOLDER']}")


    # 4. Initialize Extensions
    # Import extensions here after app is created
    from .extensions import db
    db.init_app(app)
    app.logger.info("Database Initialized.")

    # 5. Import and Register Blueprints
    # Import blueprints here
    from .routes.api import api_bp
    from .routes.frontend import frontend_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(frontend_bp)
    app.logger.info("Blueprints Registered.")

    # 6. Create Database Tables within App Context (if they don't exist)
    # Consider using Flask-Migrate for production database management
    with app.app_context():
        from . import models # Import models here to ensure app context
        from .models import Study, Configuration, Scenario

        # Check if tables need to be created
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        tables_created = False

        if not tables or 'study' not in tables:
            db.create_all()
            tables_created = True
            app.logger.info("Database tables created.")

        # If tables were just created, we don't need to do any migration
        if not tables_created:
            # Check if configuration table exists
            if 'configuration' not in tables:
                # Create only the configuration table
                metadata = db.MetaData()
                configuration_table = db.Table(
                    'configuration',
                    metadata,
                    db.Column('id', db.Integer, primary_key=True),
                    db.Column('name', db.String(100), nullable=False),
                    db.Column('phases_n', db.Integer, default=0),
                    db.Column('include_bg_dist', db.Boolean, default=False),
                    db.Column('include_bg_assign', db.Boolean, default=False),
                    db.Column('include_trip_dist', db.Boolean, default=False),
                    db.Column('trip_dist_count', db.Integer, default=1),  # Added trip_dist_count field
                    db.Column('include_trip_assign', db.Boolean, default=False),
                    db.Column('created_at', db.DateTime, default=datetime.utcnow, nullable=False),
                    db.Column('study_id', db.Integer, db.ForeignKey('study.id'), nullable=False)
                )
                metadata.create_all(db.engine)
                app.logger.info("Configuration table created.")

            # Check if configuration_id column exists in scenario table
            if 'scenario' in tables:
                scenario_columns = [col['name'] for col in inspector.get_columns('scenario')]
                if 'configuration_id' not in scenario_columns:
                    # For each study, create a default configuration
                    studies = Study.query.all()
                    for study in studies:
                        # Create a default configuration for each study
                        default_config = Configuration(
                            name="Default Configuration",
                            phases_n=0,
                            include_bg_dist=False,
                            include_bg_assign=False,
                            include_trip_dist=False,
                            trip_dist_count=1,  # Added trip_dist_count field
                            include_trip_assign=False,
                            study_id=study.id
                        )
                        db.session.add(default_config)
                        db.session.flush()  # Flush to get the configuration ID

                        # Update all scenarios for this study to use the default configuration
                        scenarios = Scenario.query.filter_by(study_id=study.id).all()
                        if scenarios:
                            # Add the configuration_id column
                            with db.engine.connect() as conn:
                                conn.execute(db.text(
                                    "ALTER TABLE scenario ADD COLUMN configuration_id INTEGER"
                                ))
                                # Set the default configuration ID for all existing scenarios
                                conn.execute(db.text(
                                    "UPDATE scenario SET configuration_id = :config_id WHERE study_id = :study_id"
                                ), {"config_id": default_config.id, "study_id": study.id})
                                # Make the column not nullable
                                conn.execute(db.text(
                                    "ALTER TABLE scenario MODIFY COLUMN configuration_id INTEGER NOT NULL"
                                ))
                                # Add the foreign key constraint
                                conn.execute(db.text(
                                    "ALTER TABLE scenario ADD CONSTRAINT fk_scenario_configuration "
                                    "FOREIGN KEY (configuration_id) REFERENCES configuration(id)"
                                ))
                                conn.commit()

                    db.session.commit()
                    app.logger.info("Added configuration_id column to Scenario table and created default configurations.")

        app.logger.info("Database schema setup completed.")

    # 7. Register error handlers
    from .error_handlers import register_error_handlers
    register_error_handlers(app)
    app.logger.info("Error handlers registered.")

    # 8. Add a simple health check or root route if desired (optional)
    @app.route('/health')
    def health_check():
        # Could add DB connection check etc.
        return "OK", 200

    app.logger.info("Flask App Creation Complete.")
    return app

# --- END OF traffic_app/__init__.py ---