# --- START OF traffic_app/extensions.py ---
from flask_sqlalchemy import SQLAlchemy

# Configure SQLAlchemy with engine options for better connection handling
db = SQLAlchemy(engine_options={
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {
        'sslmode': 'require',
        'connect_timeout': 10
    }
})
# --- END OF traffic_app/extensions.py ---