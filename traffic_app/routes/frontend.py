# --- START OF traffic_app/routes/frontend.py ---
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify, make_response, session
from ..utils import allowed_file # Import from local utils
from ..extensions import db # Needed for direct DB query for study name
from ..models import Study, Configuration # Needed for direct DB queries
from .. import api_client # Import our new API client module

frontend_bp = Blueprint('frontend', __name__)

# Custom template filter for date formatting
@frontend_bp.app_template_filter('strftime')
def _jinja2_filter_datetime(date_str, fmt=None):
    if not date_str:
        return ''
    try:
        if isinstance(date_str, str):
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            date_obj = date_str
        return date_obj.strftime(fmt or '%m/%d/%Y')
    except Exception as e:
        logging.error(f"Error formatting date {date_str}: {e}")
        return date_str

# --- Frontend Routes ---

# Flash messages route removed

@frontend_bp.route('/study/<int:study_id>/delete-confirm')
def delete_study_confirm(study_id):
    """Show confirmation dialog for deleting a study."""
    # Get study name
    study_obj = db.session.get(Study, study_id)
    if not study_obj:
        return "<div class='alert alert-danger'>Study not found</div>"

    study_name = study_obj.name
    message = f"Are you sure you want to delete the study {study_name}? This will permanently delete all configurations, scenarios, uploads, and outputs associated with this study."
    delete_url = url_for('frontend.delete_study_post', study_id=study_id)

    return render_template('partials/delete_confirmation.html',
                          message=message,
                          delete_url=delete_url,
                          method="post",
                          target="#studies-list",
                          swap="outerHTML")

@frontend_bp.route('/study/<int:study_id>/config/<int:config_id>/delete-confirm')
def delete_config_confirm(study_id, config_id):
    """Show confirmation dialog for deleting a configuration."""
    # Get configuration name
    config_obj = db.session.get(Configuration, config_id)
    if not config_obj:
        return "<div class='alert alert-danger'>Configuration not found</div>"

    config_name = config_obj.name
    message = f"Are you sure you want to delete the configuration {config_name}? This will permanently delete all scenarios, uploads, and outputs associated with this configuration."
    delete_url = url_for('frontend.delete_configuration_post', study_id=study_id, config_id=config_id)

    return render_template('partials/delete_confirmation.html',
                          message=message,
                          delete_url=delete_url,
                          method="post",
                          target="#configurations-list",
                          swap="outerHTML")

@frontend_bp.route('/study/<int:study_id>/scenario/<int:scenario_id>/delete-confirm')
def delete_scenario_confirm(study_id, scenario_id, config_id=None):
    """Show confirmation dialog for deleting a scenario."""
    # Import here to avoid circular imports
    from ..models import Scenario

    # Get scenario name
    scenario_obj = db.session.get(Scenario, scenario_id)
    if not scenario_obj:
        return "<div class='alert alert-danger'>Scenario not found</div>"

    scenario_name = scenario_obj.name
    config_id = config_id or scenario_obj.configuration_id

    message = f"Are you sure you want to delete the scenario {scenario_name}? This will permanently delete all uploads and outputs associated with this scenario."
    delete_url = url_for('frontend.delete_scenario_post', study_id=study_id, scenario_id=scenario_id)

    # Target the scenarios container for this configuration
    target = f"#config-{config_id} .scenarios-container"

    return render_template('partials/delete_confirmation.html',
                          message=message,
                          delete_url=delete_url,
                          method="post",
                          target=target,
                          swap="innerHTML")

# Clear flashes route removed

@frontend_bp.route('/search-studies')
def search_studies():
    """Route to search studies by name or analyst."""
    search_query = request.args.get('q', '').strip().lower()

    # Fetch all studies from API (already sorted by created_at desc)
    studies, error = api_client.get_studies()

    if error:
        logging.error(f"Error in search_studies: {error}")
    elif search_query:
        # Filter studies based on search query
        filtered_studies = []
        for study in studies:
            study_name = study.get('name', '').lower()
            analyst_name = study.get('analyst_name', '').lower()
            if search_query in study_name or search_query in analyst_name:
                filtered_studies.append(study)
        studies = filtered_studies

    return render_template('partials/studies_list.html', studies=studies)

@frontend_bp.route('/')
def index():
    """Render the home page with a list of studies."""
    studies, error = api_client.get_studies()

    if error:
        flash(error, 'error')

    return render_template('index.html', studies=studies)

@frontend_bp.route('/study/<int:study_id>')
def study(study_id):
    """Renders the page for a specific study."""
    # Fetch study details directly from DB
    study_obj = db.session.get(Study, study_id)
    if not study_obj:
        flash('Study not found.', 'error')
        return redirect(url_for('frontend.index'))

    study_name = study_obj.name
    analyst_name = study_obj.analyst_name

    # Fetch configurations via API client
    configurations, error = api_client.get_configurations(study_id)

    if error:
        flash(error, 'error')
        return redirect(url_for('frontend.index'))

    return render_template('study.html', study_id=study_id, study_name=study_name,
                          analyst_name=analyst_name, configurations=configurations)


@frontend_bp.route('/study/create', methods=['POST'])
def create_study_frontend():
    """Create a new study."""
    study_name = request.form.get('name')
    analyst_name = request.form.get('analyst_name')

    if not study_name or not study_name.strip():
        message = 'Study name is required.'
        status = 'danger'
    elif not analyst_name or not analyst_name.strip():
        message = 'Analyst name is required.'
        status = 'danger'
    else:
        data, error, status_code = api_client.create_study(study_name, analyst_name)

        if status_code == 201:
            message = 'Study created successfully!'
            status = 'success'
        elif status_code == 409:
            message = error or 'Study name already exists.'
            status = 'danger'
        else:
            message = error or f'Error creating study (API Status: {status_code}).'
            status = 'danger'

    # Add flash message
    flash(message, status)

    # If it's an HTMX request, return the updated studies list with HX-Trigger for flash message
    if request.headers.get('HX-Request'):
        # Fetch the updated studies list
        studies, error = api_client.get_studies()
        if error:
            logging.error(f"Error fetching studies for HTMX response: {error}")

        response = make_response(render_template('partials/studies_list.html', studies=studies))
        return response

    # For regular requests, redirect to index
    return redirect(url_for('frontend.index'))

@frontend_bp.route('/study/<int:study_id>/configure', methods=['POST'])
def configure_study_frontend(study_id):
    """Configure a study with scenarios."""
    config_name = request.form.get('config_name', '').strip()
    if not config_name:
        flash('Configuration name is required.', 'error')
        if request.headers.get('HX-Request'):
            response = make_response(render_template('partials/configurations_list.html', configurations=[], study_id=study_id))
            return response
        return redirect(url_for('frontend.study', study_id=study_id))

    try: phases_n = request.form.get('phases_n', type=int)
    except ValueError: phases_n = None
    include_bg_dist = 'include_bg_dist' in request.form
    include_bg_assign = 'include_bg_assign' in request.form
    include_trip_dist = 'include_trip_dist' in request.form
    include_trip_assign = 'include_trip_assign' in request.form

    # Get trip distribution count if trip distribution is included
    try:
        trip_dist_count = request.form.get('trip_dist_count', type=int) if include_trip_dist else 1
        if trip_dist_count < 1:
            trip_dist_count = 1
    except ValueError:
        trip_dist_count = 1

    if phases_n is None or phases_n < 0:
        flash('Number of phases must be a valid non-negative number.', 'error')
        if request.headers.get('HX-Request'):
            response = make_response(render_template('partials/configurations_list.html', configurations=[], study_id=study_id))
            return response
    else:
        config_data = {
            'config_name': config_name,
            'phases_n': phases_n,
            'include_bg_dist': include_bg_dist,
            'include_bg_assign': include_bg_assign,
            'include_trip_dist': include_trip_dist,
            'trip_dist_count': trip_dist_count,
            'include_trip_assign': include_trip_assign
        }

        data, error, status_code = api_client.configure_study(study_id, config_data)

        if status_code == 200:
            message = f'Configuration "{config_name}" created successfully!'
            status = 'success'
        else:
            message = error or f'Error creating configuration.'
            status = 'danger'

        # Add flash message
        flash(message, status)

    # If it's an HTMX request, return the updated configurations list with HX-Trigger for flash message
    if request.headers.get('HX-Request'):
        # Fetch the updated configurations list
        configurations, error = api_client.get_configurations(study_id)
        if error:
            logging.error(f"Error fetching configurations for HTMX response: {error}")

        response = make_response(render_template('partials/configurations_list.html', configurations=configurations, study_id=study_id))
        return response

    # For regular requests, redirect to study page
    return redirect(url_for('frontend.study', study_id=study_id))


@frontend_bp.route('/study/<int:study_id>/configuration/<int:config_id>/scenarios')
def get_scenarios_for_config(study_id, config_id):
    """Get scenarios for a specific configuration."""
    scenarios, error = api_client.get_scenarios(study_id, config_id)

    if error:
        logging.error(f"Error fetching scenarios for configuration {config_id}: {error}")
        return f"<div class='alert alert-danger'>Error loading scenarios: {error}</div>"

    # Calculate completion percentage
    total_scenarios = len(scenarios)
    completed_scenarios = sum(1 for scenario in scenarios if scenario.get('status') == 'COMPLETE')
    completion_percentage = (completed_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0

    # Add a hidden spinner element to prevent HTMX indicator errors
    result = f"""
    <div class="scenarios-spinner-{config_id}" style="display:none;"></div>
    {render_template('partials/config_scenarios_list.html', scenarios=scenarios, study_id=study_id)}
    <script>
        (function() {{
            // Update progress bar
            const progressBar_{config_id} = document.getElementById('progress-bar-{config_id}');
            if (progressBar_{config_id}) {{
                progressBar_{config_id}.style.width = '{completion_percentage:.1f}%';
            }}
        }})();
    </script>
    """
    return result

@frontend_bp.route('/study/<int:study_id>/scenario/<int:scenario_id>')
def scenario(study_id, scenario_id):
    """Renders the page for a specific scenario."""
    # Get study name for breadcrumb
    study_name = f"Study {study_id}"  # Default
    try:
        study_obj = db.session.get(Study, study_id)
        if study_obj:
            study_name = study_obj.name
    except Exception as e:
        logging.error(f"Error fetching study name for breadcrumb: {e}")

    # Get scenario data
    try:
        scenario_data, error = api_client.get_scenario_status(study_id, scenario_id)

        if error:
            logging.error(f"Error getting scenario status: {error}")
            # Return an error message instead of redirecting
            if request.headers.get('HX-Request'):
                return f"<div class='alert alert-danger'>Error loading scenario: {error}</div>"
            return redirect(url_for('frontend.study', study_id=study_id))

        return render_template('scenario.html', scenario=scenario_data, study_id=study_id, study_name=study_name)
    except Exception as e:
        logging.error(f"Unexpected error in scenario route: {e}")
        # Return an error message instead of redirecting
        if request.headers.get('HX-Request'):
            return f"<div class='alert alert-danger'>An unexpected error occurred: {str(e)}</div>"
        return redirect(url_for('frontend.study', study_id=study_id))

@frontend_bp.route('/study/<int:study_id>/scenario/<int:scenario_id>/upload', methods=['POST'])
def upload_file_frontend(study_id, scenario_id):
    """Handles file upload form submission for AM CSV, PM CSV, or ATTOUT TXT."""
    error_message = None
    try:
        file_type = request.form.get('file_type')

        if 'file' not in request.files:
            error_message = 'No file part in the request.'
            logging.error(error_message)
        else:
            file = request.files['file']
            if file.filename == '':
                error_message = 'No file selected.'
                logging.error(error_message)
            # Use the utility function imported from the package
            elif file and allowed_file(file.filename):
                # If file_type is missing or invalid, detect it from the file
                if not file_type or file_type not in ['am_csv', 'pm_csv', 'attout_txt']:
                    file_type = detect_file_type_from_file(file)
                    logging.info(f"Auto-detected file type: {file_type}")

                # Validate file extension against the file type
                expected_ext = 'csv' if file_type in ['am_csv', 'pm_csv'] else 'txt'
                actual_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

                if actual_ext != expected_ext:
                    error_message = f'Invalid extension for {file_type}. Expected .{expected_ext}'
                    logging.error(error_message)
                else:
                    # Upload the file with the detected or provided type
                    data, error = api_client.upload_file(study_id, scenario_id, file_type, file)
                    if error:
                        error_message = error
                        logging.error(f"API error during upload: {error}")
                    else:
                        logging.info(f'File uploaded successfully as {file_type}!')
            else:
                error_message = f'Invalid file type. Allowed: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}'
                logging.error(error_message)
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        logging.error(f"Unexpected error in upload_file_frontend: {e}")

    # If it's an HTMX request, return the combined status and process form
    if request.headers.get('HX-Request'):
        # Fetch the updated scenario status
        scenario_data, error = api_client.get_scenario_status(study_id, scenario_id)
        if error:
            logging.error(f"Error fetching scenario status for HTMX response: {error}")
            # Return a basic error message if we can't fetch the updated status
            return f"<div id='file-upload-and-actions'><p class='text-danger'>Error updating status: {error}</p></div>"

        # Render both the status and process form templates and return them together
        status_html = render_template('partials/scenario_status.html', scenario=scenario_data, study_id=study_id)
        process_form_html = render_template('partials/scenario_process_form.html', scenario=scenario_data, study_id=study_id)

        return f"<div id='file-upload-and-actions'>{status_html}{process_form_html}</div>"

    # For regular requests, redirect to scenario page
    return redirect(url_for('frontend.scenario', study_id=study_id, scenario_id=scenario_id))

def detect_file_type_from_file(file):
    """Detect the file type based on file extension and content.

    Args:
        file: The file object from request.files

    Returns:
        str: Detected file type ('am_csv', 'pm_csv', or 'attout_txt')
    """
    # Save the current position
    current_position = file.tell()

    # First check the file extension
    filename = file.filename.lower()
    if filename.endswith('.txt'):
        file_type = 'attout_txt'
    else:  # Assume CSV
        # Try to detect PM vs AM from filename - check PM first to avoid false positives
        # Use more specific patterns to avoid matching 'am' in words like 'Sample'
        if '_pm' in filename or 'pm_' in filename or ' pm' in filename:
            file_type = 'pm_csv'
        elif '_am' in filename or 'am_' in filename or ' am' in filename:
            file_type = 'am_csv'
        else:
            # Default to AM CSV if we can't determine
            file_type = 'am_csv'

    # Reset file position
    file.seek(current_position)

    return file_type


@frontend_bp.route('/study/<int:study_id>/scenario/<int:scenario_id>/process', methods=['POST'])
def process_scenario_frontend(study_id, scenario_id):
    """Handles the button click to trigger scenario processing."""
    try:
        data, error = api_client.process_scenario(study_id, scenario_id)

        if error:
            logging.error(f"Processing Failed: {error}")
        else:
            # Check for ATTIN path as sign of success
            if data.get('attin_txt_path'):
                logging.info('Processing completed successfully! ATTIN file generated.')
            else:
                # This case shouldn't happen if API returns 200 correctly
                logging.warning(f"Frontend: API returned success but missing 'attin_txt_path' in response JSON")
    except Exception as e:
        logging.error(f"Unexpected error in process_scenario_frontend: {e}")
        error = f"An unexpected error occurred: {str(e)}"

    # If it's an HTMX request, update both status and downloads sections
    if request.headers.get('HX-Request'):
        # Fetch the updated scenario status
        scenario_data, error = api_client.get_scenario_status(study_id, scenario_id)
        if error:
            logging.error(f"Error fetching scenario status for HTMX response: {error}")
            # Return a basic error message in the target element
            return "<p class='text-danger'>Error processing scenario</p>"

        # Get configuration ID to update progress bar
        config_id = scenario_data.get('configuration_id')
        
        # Fetch all scenarios for this configuration to calculate progress
        if config_id:
            scenarios, scenarios_error = api_client.get_scenarios(study_id, config_id)
            if not scenarios_error:
                total_scenarios = len(scenarios)
                completed_scenarios = sum(1 for scenario in scenarios if scenario.get('status') == 'COMPLETE')
                completion_percentage = (completed_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0
            else:
                completion_percentage = 0
        else:
            completion_percentage = 0

        # Render both the status/action section and downloads section with updated data
        status_html = render_template('partials/scenario_status.html', scenario=scenario_data, study_id=study_id)
        process_form_html = render_template('partials/scenario_process_form.html', scenario=scenario_data, study_id=study_id)
        downloads_html = render_template('partials/scenario_downloads.html', scenario=scenario_data, study_id=study_id)

        # Compose the response with OOB swaps for multiple elements
        response = """
        <!-- Main response for the target element -->
        <span>Processing complete</span>

        <!-- Out-of-band updates -->
        <div id="file-upload-and-actions" hx-swap-oob="innerHTML">
            {status_html}
            {process_html}
        </div>
        <div id="scenario-downloads" hx-swap-oob="innerHTML">
            {downloads_html}
        </div>
        <script>
            (function() {{
                // Update progress bar
                const progressBar_{config_id} = document.getElementById('progress-bar-{config_id}');
                if (progressBar_{config_id}) {{
                    progressBar_{config_id}.style.width = '{completion_percentage:.1f}%';
                }}
            }})();
        </script>
        """.format(
            status_html=status_html,
            process_html=process_form_html,
            downloads_html=downloads_html,
            config_id=config_id,
            completion_percentage=completion_percentage
        )

        return response

    # For regular requests, redirect to scenario page
    return redirect(url_for('frontend.scenario', study_id=study_id, scenario_id=scenario_id))


@frontend_bp.route('/study/<int:study_id>/config/<int:config_id>', methods=['DELETE'])
def delete_configuration(study_id, config_id):
    """Handles the deletion of a configuration."""
    data, error = api_client.delete_configuration(study_id, config_id)

    if error:
        flash(error, 'error')
    else:
        flash('Configuration deleted successfully!', 'success')

    # Return the updated configurations list
    configurations, error = api_client.get_configurations(study_id)
    if error:
        logging.error(f"Error fetching configurations after deletion: {error}")

    return render_template('partials/configurations_list.html', configurations=configurations, study_id=study_id)

@frontend_bp.route('/study/<int:study_id>/scenario/<int:scenario_id>', methods=['DELETE'])
def delete_scenario(study_id, scenario_id):
    """Handles the deletion of a scenario."""
    logging.info(f"Frontend: DELETE request received for scenario {scenario_id} in study {study_id}")

    data, error = api_client.delete_scenario(study_id, scenario_id)

    if error:
        flash(error, 'error')
        logging.error(f"Frontend: Error deleting scenario {scenario_id}: {error}")

        # If we couldn't delete the scenario and it's an HTMX request, return an error message
        if request.headers.get('HX-Request'):
            return f"<div class='alert alert-danger'>Error refreshing scenarios list after deletion.</div>"
    else:
        flash('Scenario deleted successfully!', 'success')
        # Get the configuration ID from the response
        config_id = data.get('configuration_id')
        logging.info(f"Frontend: Scenario deleted successfully, config_id: {config_id}")

        # If we have a configuration ID, return the updated scenarios list for that configuration
        if config_id and request.headers.get('HX-Request'):
            logging.info(f"Frontend: Returning updated scenarios list for config {config_id}")
            return get_scenarios_for_config(study_id, config_id)

    # If we couldn't get the configuration ID or there was an error, redirect to the study page
    if request.headers.get('HX-Request'):
        logging.info(f"Frontend: Returning error message for HTMX request")
        return f"<div class='alert alert-danger'>Error refreshing scenarios list after deletion.</div>"

    logging.info(f"Frontend: Redirecting to study page")
    return redirect(url_for('frontend.study', study_id=study_id))

@frontend_bp.route('/study/<int:study_id>/scenario/<int:scenario_id>/delete', methods=['POST'])
def delete_scenario_post(study_id, scenario_id):
    """Handles the POST request for deleting a scenario."""
    logging.info(f"Frontend: POST request received for deleting scenario {scenario_id} in study {study_id}")

    # First, get the configuration ID for this scenario
    config_id = None
    scenario_data, error = api_client.get_scenario_status(study_id, scenario_id)
    if not error:
        config_id = scenario_data.get('configuration_id')
        logging.info(f"Frontend: Found configuration ID {config_id} for scenario {scenario_id}")
    else:
        logging.error(f"Frontend: Error getting configuration ID for scenario {scenario_id}: {error}")

    # Now delete the scenario
    data, error = api_client.delete_scenario(study_id, scenario_id)

    if error:
        message = f'Error deleting scenario: {error}'
        status = 'danger'
        logging.error(f"Frontend: Error deleting scenario {scenario_id}: {error}")
    else:
        message = 'Scenario deleted successfully!'
        status = 'success'
        logging.info(f"Frontend: Scenario {scenario_id} deleted successfully")

        # If we have the configuration ID from the scenario or from the API response
        if not config_id:
            config_id = data.get('configuration_id')

    # Add flash message
    flash(message, status)

    # If it's an HTMX request and we have a configuration ID, return the updated scenarios list
    if request.headers.get('HX-Request') and config_id:
        logging.info(f"Frontend: Returning updated scenarios list for config {config_id}")
        scenarios, error = api_client.get_scenarios(study_id, config_id)
        if error:
            logging.error(f"Error fetching scenarios for configuration {config_id}: {error}")
            response = make_response(f"<div class='alert alert-danger'>Error loading scenarios: {error}</div>")
        else:
            # Add a hidden spinner element to prevent HTMX indicator errors
            html_content = f"""
            <div class="scenarios-spinner-{config_id}" style="display:none;"></div>
            {render_template('partials/config_scenarios_list.html', scenarios=scenarios, study_id=study_id)}
            """
            response = make_response(html_content)

        # Flash message trigger removed
        return response

    # If it's an HTMX request but we couldn't get the configuration ID, return an error message
    if request.headers.get('HX-Request'):
        response = make_response(f"<div class='alert alert-danger'>Error refreshing scenarios list after deletion.</div>")
        # Flash message trigger removed
        return response

    # For regular requests or if something went wrong, redirect back to the study page
    return redirect(url_for('frontend.study', study_id=study_id))

@frontend_bp.route('/study/<int:study_id>/config/<int:config_id>/delete', methods=['POST'])
def delete_configuration_post(study_id, config_id):
    """Handles the POST request for deleting a configuration."""
    logging.info(f"Frontend: POST request received for deleting configuration {config_id} in study {study_id}")

    data, error = api_client.delete_configuration(study_id, config_id)

    if error:
        message = f'Error deleting configuration: {error}'
        status = 'danger'
        logging.error(f"Frontend: Error deleting configuration {config_id}: {error}")
    else:
        message = 'Configuration deleted successfully!'
        status = 'success'
        logging.info(f"Frontend: Configuration {config_id} deleted successfully")

    # Add flash message
    flash(message, status)

    # If it's an HTMX request, return the updated configurations list with HX-Trigger for flash message
    if request.headers.get('HX-Request'):
        # Fetch the updated configurations list
        configurations, error = api_client.get_configurations(study_id)
        if error:
            logging.error(f"Error fetching configurations for HTMX response: {error}")

        response = make_response(render_template('partials/configurations_list.html', configurations=configurations, study_id=study_id))
        # Flash message trigger removed
        return response

    # For regular requests, redirect to study page
    return redirect(url_for('frontend.study', study_id=study_id))

@frontend_bp.route('/study/<int:study_id>/configurations')
def get_configurations_list(study_id):
    """Get configurations list for a specific study."""
    logging.info(f"Frontend: GET request received for configurations list for study {study_id}")

    configurations, error = api_client.get_configurations(study_id)

    if error:
        logging.error(f"Error fetching configurations for study {study_id}: {error}")
        flash(f"Error loading configurations: {error}", "error")

    return render_template('partials/configurations_list.html', configurations=configurations, study_id=study_id)

@frontend_bp.route('/study/<int:study_id>/delete', methods=['POST'])
def delete_study_post(study_id):
    """Handles the POST request for deleting a study."""
    logging.info(f"Frontend: POST request received for deleting study {study_id}")

    data, error = api_client.delete_study(study_id)

    if error:
        message = f'Error deleting study: {error}'
        status = 'danger'
        logging.error(f"Frontend: Error deleting study {study_id}: {error}")
    else:
        message = 'Study deleted successfully!'
        status = 'success'
        logging.info(f"Frontend: Study {study_id} deleted successfully")

    # Add flash message
    flash(message, status)

    # If it's an HTMX request, return the updated studies list with HX-Trigger for flash message
    if request.headers.get('HX-Request'):
        # Fetch the updated studies list
        studies, error = api_client.get_studies()
        if error:
            logging.error(f"Error fetching studies for HTMX response: {error}")

        response = make_response(render_template('partials/studies_list.html', studies=studies))
        # Flash message trigger removed
        return response

    # For regular requests, redirect to index
    return redirect(url_for('frontend.index'))

@frontend_bp.route('/study/<int:study_id>/scenario/<int:scenario_id>/delete_file/<string:file_type_id>', methods=['POST'])
def delete_scenario_file_interactive(study_id, scenario_id, file_type_id):
    """Handles interactive deletion of a specific uploaded file for a scenario."""
    logging.info(f"Frontend: Received request to delete file_type '{file_type_id}' for scenario {scenario_id}, study {study_id}")

    # Call an API client method to handle the actual deletion logic
    # This keeps the frontend route cleaner and reuses logic if an API endpoint for this is also desired later.
    # We'll need to create this api_client.delete_uploaded_file function.
    success, message_or_data = api_client.delete_scenario_file_api(study_id, scenario_id, file_type_id)

    if not success:
        # If the API call itself fails badly or returns a clear error message to flash
        flash(message_or_data or f"Error deleting file '{file_type_id}'.", 'danger')
        # How to respond here? If API gives full HTML error, maybe return that.
        # For now, let's assume we need to re-render the status.
        # Fallback: Get current status and re-render. This might not show a specific error from deletion though.
        scenario_data, fetch_error = api_client.get_scenario_status(study_id, scenario_id)
        if fetch_error:
            logging.error(f"Error fetching scenario status after failed deletion: {fetch_error}")
            return f"<div id='file-upload-and-actions'><p class='text-danger'>Error deleting file and then error updating status: {fetch_error}</p></div>", 500
        flash(f"Could not delete file: {message_or_data}", "danger") # Ensure error is flashed
    else:
        # API call was successful (file deleted, DB updated by API)
        api_response = message_or_data # On success, API client should return the updated scenario data
        # Convert the API response to the format expected by the template
        scenario_data = {
            'id': api_response['scenario_id'],
            'name': api_response['name'],
            'status': api_response['status'],
            'status_message': api_response['status_message'],
            'uploaded_files': api_response['uploaded_files'],
            'has_am_csv': api_response['has_am_csv'],
            'has_pm_csv': api_response['has_pm_csv'],
            'has_attout': api_response['has_attout'],
            'has_merged': api_response['has_merged'],
            'has_attin': api_response['has_attin']
        }
        flash(f"File '{file_type_id}' deleted successfully.", 'success')

    # Always re-render the target area with updated (or current) scenario data
    # This ensures the file list and status reflect the change (or lack thereof if deletion failed but status was fetched)
    status_html = render_template('partials/scenario_status.html', scenario=scenario_data, study_id=study_id)
    process_form_html = render_template('partials/scenario_process_form.html', scenario=scenario_data, study_id=study_id)
    
    # Ensure the response is correctly recognized as an HTMX partial by setting the HX-Trigger header for flashes
    # And by returning the HTML snippet that HTMX expects to swap.
    response = make_response(f"<div id='file-upload-and-actions'>{status_html}{process_form_html}</div>")
    if request.headers.get('HX-Request'):
        response.headers['HX-Trigger'] = 'flashMessage' # Assuming you have JS to handle this for flashes
    
    return response

# --- END OF traffic_app/routes/frontend.py ---