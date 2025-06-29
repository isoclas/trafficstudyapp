# --- START OF traffic_app/error_handlers.py ---
import logging
from flask import render_template, jsonify, request
from werkzeug.exceptions import HTTPException

def register_error_handlers(app):
    """Register error handlers for the application."""
    
    @app.errorhandler(400)
    def bad_request_error(error):
        return handle_error(error, 400, 'Bad Request')
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        return handle_error(error, 401, 'Unauthorized')
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return handle_error(error, 403, 'Forbidden')
    
    @app.errorhandler(404)
    def not_found_error(error):
        return handle_error(error, 404, 'Not Found')
    
    @app.errorhandler(405)
    def method_not_allowed_error(error):
        return handle_error(error, 405, 'Method Not Allowed')
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return handle_error(error, 500, 'Internal Server Error')
    
    @app.errorhandler(Exception)
    def unhandled_exception(error):
        logging.exception("Unhandled exception: %s", str(error))
        return handle_error(error, 500, 'Internal Server Error')

def handle_error(error, default_code=500, default_message='Internal Server Error'):
    """Centralized error handling function.
    
    Args:
        error: The error object
        default_code: Default HTTP status code if not provided by the error
        default_message: Default error message if not provided by the error
        
    Returns:
        Appropriate response based on request type (API, HTMX, or regular)
    """
    # Get error code and description
    code = getattr(error, 'code', default_code)
    description = getattr(error, 'description', str(error) or default_message)
    
    # Log the error
    logging.error("Error %s: %s", code, description)
    
    # Check if this is an API request (URL starts with /api)
    if request.path.startswith('/api'):
        return jsonify({
            'error': description,
            'status_code': code
        }), code
    
    # Check if this is an HTMX request
    if request.headers.get('HX-Request'):
        # For HTMX requests, return a simple error message that can be inserted into the DOM
        return f"""
        <div class="alert alert-danger" role="alert">
            <h4 class="alert-heading">{default_message}</h4>
            <p>{description}</p>
        </div>
        """, code
    
    # For regular requests, render the error template
    return render_template('error.html', 
                          error_code=code,
                          error_name=default_message,
                          error_description=description), code

# --- END OF traffic_app/error_handlers.py ---
