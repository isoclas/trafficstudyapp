import os
import secrets
from typing import Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class Config:
    """Base configuration class with common settings."""
    
    # Security Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Warn if using default secret key in production
    @classmethod
    def validate_secret_key(cls) -> None:
        """Validate that a proper secret key is configured."""
        if not os.environ.get('SECRET_KEY'):
            import warnings
            warnings.warn(
                "SECRET_KEY not set in environment variables. "
                "Using generated key which will change on restart.",
                UserWarning
            )

    # Database Configuration
    @classmethod
    def get_database_uri(cls) -> str:
        """Get the database URI with proper SSL configuration."""
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Handle PostgreSQL URL conversion and SSL
            if database_url.startswith('postgresql://'):
                database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://')
                if '?' not in database_url:
                    database_url += '?sslmode=require'
                elif 'sslmode=' not in database_url:
                    database_url += '&sslmode=require'
            return database_url
        
        # Default to SQLite for local development
        sqlite_path = os.path.join(BASE_DIR, "instance", "traffic_app.db")
        os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
        return f'sqlite:///{sqlite_path}'
    
    SQLALCHEMY_DATABASE_URI = get_database_uri.__func__()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Verify connections before use
        'pool_recycle': 300,    # Recycle connections every 5 minutes
    }

    # File storage configuration
    USE_CLOUDINARY = os.environ.get('USE_CLOUDINARY', 'False').lower() == 'true'
    
    # Cloudinary configuration
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    
    # Local storage fallback
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
    ALLOWED_EXTENSIONS = {'csv', 'txt'}

    LOGGING_LEVEL = 'DEBUG'
    LOGGING_FORMAT = '%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s'


class DevelopmentConfig(Config):
    """Development configuration with debugging features."""
    DEBUG = True
    TESTING = False
    LOGGING_LEVEL = 'DEBUG'
    
    # Development-specific settings
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # More verbose logging for development
    LOGGING_FORMAT = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s'
    
    # SQLAlchemy settings for development
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    
    @classmethod
    def init_app(cls, app):
        """Initialize development-specific settings."""
        # Warn about missing environment variables but don't fail
        if not os.environ.get('SECRET_KEY'):
            app.logger.warning(
                "SECRET_KEY not set. Using generated key for development."
            )


class ProductionConfig(Config):
    """Production configuration with security and performance optimizations."""
    DEBUG = False
    TESTING = False
    LOGGING_LEVEL = 'INFO'
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # Ensure Cloudinary is used in production
    USE_CLOUDINARY = os.environ.get('USE_CLOUDINARY', 'True').lower() == 'true'
    
    # Use internal API calls to avoid SSL issues in production
    USE_INTERNAL_API = True
    
    # Production logging format
    LOGGING_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    
    # Performance optimizations
    SQLALCHEMY_ENGINE_OPTIONS = {
        **Config.SQLALCHEMY_ENGINE_OPTIONS,
        'pool_size': 10,
        'max_overflow': 20,
    }
    
    @classmethod
    def init_app(cls, app):
        """Initialize production-specific settings."""
        Config.validate_secret_key()
        
        # Ensure required environment variables are set
        required_vars = ['SECRET_KEY']
        if cls.USE_CLOUDINARY:
            required_vars.extend([
                'CLOUDINARY_CLOUD_NAME',
                'CLOUDINARY_API_KEY', 
                'CLOUDINARY_API_SECRET'
            ])
        
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )


class TestingConfig(Config):
    """Testing configuration for unit and integration tests."""
    TESTING = True
    DEBUG = True
    LOGGING_LEVEL = 'WARNING'  # Reduce log noise during testing
    
    # Use in-memory database for faster tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': False,  # Not needed for in-memory DB
    }
    
    # Disable CSRF for easier testing
    WTF_CSRF_ENABLED = False
    
    # Disable Cloudinary for testing
    USE_CLOUDINARY = False
    
    # Fast password hashing for tests
    BCRYPT_LOG_ROUNDS = 4
    
    @classmethod
    def init_app(cls, app):
        """Initialize testing-specific settings."""
        # Suppress most logging during tests
        import logging
        logging.getLogger('werkzeug').setLevel(logging.ERROR)


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}

# Ensure necessary directories exist (can also be done in __init__.py)
# os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
# os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
# os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)

# --- END OF traffic_app/config.py ---