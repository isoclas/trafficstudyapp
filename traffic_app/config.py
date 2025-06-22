# --- START OF traffic_app/config.py ---
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # Point to project root

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'final-secret-key-change-me-please') # Use env var or default

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(BASE_DIR, "instance", "traffic_app.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')
    ALLOWED_EXTENSIONS = {'csv', 'txt'}

    LOGGING_LEVEL = 'DEBUG'
    LOGGING_FORMAT = '%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s'

# Ensure necessary directories exist (can also be done in __init__.py)
# os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
# os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
# os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)

# --- END OF traffic_app/config.py ---