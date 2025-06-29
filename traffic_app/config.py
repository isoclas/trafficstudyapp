import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'final-secret-key-change-me-please')

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(BASE_DIR, "instance", "traffic_app.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
    """Development configuration."""
    DEBUG = True
    LOGGING_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOGGING_LEVEL = 'INFO'
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Ensure Cloudinary is used in production
    USE_CLOUDINARY = os.environ.get('USE_CLOUDINARY', 'True').lower() == 'true'
    
    # Production logging format
    LOGGING_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


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