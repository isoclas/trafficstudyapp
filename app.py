#!/usr/bin/env python3
"""
Flask Application Entry Point

This module serves as the entry point for the Traffic Study Application.
It creates and configures the Flask application using the application factory pattern.
"""

import os
import sys
from typing import Optional

try:
    from traffic_app import create_app
except ImportError as e:
    print(f"Error importing traffic_app: {e}", file=sys.stderr)
    sys.exit(1)


def get_config_name() -> str:
    """Determine the configuration name based on environment variables."""
    # Check for explicit configuration override
    config_name = os.environ.get('FLASK_CONFIG')
    if config_name:
        return config_name
    
    # Fall back to FLASK_ENV for backward compatibility
    flask_env = os.environ.get('FLASK_ENV', 'production')
    return flask_env


def get_debug_mode(app_config_debug: bool) -> bool:
    """Determine debug mode with proper precedence."""
    # FLASK_DEBUG environment variable takes highest precedence
    flask_debug_env = os.environ.get('FLASK_DEBUG')
    if flask_debug_env is not None:
        return flask_debug_env.lower() not in ('0', 'false', 'no', '')
    
    # Fall back to application configuration
    return app_config_debug


def get_server_config() -> tuple[str, int]:
    """Get server host and port configuration."""
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    
    try:
        port = int(os.environ.get('FLASK_RUN_PORT', '5000'))
        if not (1 <= port <= 65535):
            raise ValueError(f"Port {port} is out of valid range (1-65535)")
    except ValueError as e:
        print(f"Invalid port configuration: {e}", file=sys.stderr)
        port = 5000
    
    return host, port


def create_application(config_name: Optional[str] = None) -> 'Flask':
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = get_config_name()
    
    try:
        app = create_app(config_name)
        return app
    except Exception as e:
        print(f"Failed to create Flask application: {e}", file=sys.stderr)
        sys.exit(1)


# Create the application instance using the factory pattern
app = create_application()


if __name__ == '__main__':
    # Get server configuration
    host, port = get_server_config()
    
    # Determine debug mode
    debug = get_debug_mode(app.config.get('DEBUG', False))
    
    # Log startup information
    app.logger.info(
        f"Starting Flask app on {host}:{port} "
        f"(Debug: {debug}, Config: {app.config.get('ENV', 'unknown')})"
    )
    
    # Configure run parameters based on debug mode
    run_kwargs = {
        'debug': debug,
        'host': host,
        'port': port,
        'threaded': True,  # Enable threading for better performance
    }
    
    # Development-specific configurations
    if debug:
        run_kwargs.update({
            'use_reloader': True,
            'extra_files': ['static/dist/output.css'],  # Watch for CSS changes
            'reloader_type': 'stat',  # More reliable than watchdog on some systems
        })
    
    try:
        app.run(**run_kwargs)
    except KeyboardInterrupt:
        app.logger.info("Application shutdown requested by user")
    except Exception as e:
        app.logger.error(f"Application failed to start: {e}")
        sys.exit(1)