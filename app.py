import os
from traffic_app import create_app

# Create the application instance using the factory
# This will use the default 'traffic_app.config.Config' unless FLASK_CONFIG is set
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True, extra_files=['static/dist/output.css'])
    # Configuration for running locally is now primarily handled by:
    # 1. traffic_app/config.py (for defaults)
    # 2. instance/config.py (for local overrides, create if needed)
    # 3. Environment variables (FLASK_RUN_HOST, FLASK_RUN_PORT, FLASK_DEBUG)

    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', True) # Default to True for local run via app.py

    # Override with environment variables if they are set
    host = os.environ.get('FLASK_RUN_HOST', host)
    port = int(os.environ.get('FLASK_RUN_PORT', port))
    # FLASK_DEBUG=0 means False, FLASK_DEBUG=1 (or any non-empty string other than '0') means True
    flask_debug_env = os.environ.get('FLASK_DEBUG')
    if flask_debug_env is not None:
        debug = flask_debug_env.lower() not in ('0', 'false', 'no')

    app.logger.info(f"Starting Flask app on {host}:{port} (Debug: {debug})")
    app.run(debug=debug, host=host, port=port)