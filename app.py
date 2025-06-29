import os
from traffic_app import create_app

# Create the application instance using the factory
# This will use production config by default unless FLASK_ENV is set
app = create_app()

if __name__ == '__main__':
    # Get configuration from environment or use defaults
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    
    # Debug mode is controlled by the configuration class
    debug = app.config.get('DEBUG', False)
    
    # Override debug if FLASK_DEBUG is explicitly set
    flask_debug_env = os.environ.get('FLASK_DEBUG')
    if flask_debug_env is not None:
        debug = flask_debug_env.lower() not in ('0', 'false', 'no')

    app.logger.info(f"Starting Flask app on {host}:{port} (Debug: {debug})")
    
    # Only use reloader and extra_files in development
    if debug:
        app.run(debug=debug, host=host, port=port, use_reloader=True, extra_files=['static/dist/output.css'])
    else:
        app.run(debug=debug, host=host, port=port)