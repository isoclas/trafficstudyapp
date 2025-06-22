import os

class PythonAnywhereConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-production-secret-key-here')

    # Use MySQL database on PythonAnywhere - Updated with correct database name
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://trafficstudyapp:1qwertyuiop0@trafficstudyapp.mysql.pythonanywhere-services.com/trafficstudyapp$traffic_app_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # PythonAnywhere paths
    BASE_DIR = '/home/trafficstudyapp/trafficstudies'
    UPLOAD_FOLDER = '/home/trafficstudyapp/trafficstudies/uploads'
    OUTPUT_FOLDER = '/home/trafficstudyapp/trafficstudies/outputs'
    ALLOWED_EXTENSIONS = {'csv', 'txt', 'xml'}

    # Production logging
    LOGGING_LEVEL = 'INFO'
    LOGGING_FORMAT = '%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s'

    # Disable self-referencing API calls
    USE_INTERNAL_API = True