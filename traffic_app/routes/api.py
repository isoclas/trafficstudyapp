# --- START OF traffic_app/routes/api.py ---
import os
import logging
# V-- Make sure this line correctly imports Blueprint --V
from flask import Blueprint, request, jsonify, abort, send_from_directory, current_app
from werkzeug.utils import secure_filename
from ..extensions import db  # Import from the extensions module in the parent directory
from ..models import Study, Scenario, Configuration, ProcessingStatus # Import from models module
from ..utils import get_scenario_folder_path         # Import from utils module
from traffic_app.processing import process_traffic_data # Use absolute import
from ..utils import (
    validate_file_extension, 
    save_uploaded_file, 
    get_scenario_folder_path, 
    get_absolute_path, 
    get_relative_path, 
    get_download_info,
    delete_scenario_files, 
    delete_scenario_folders, 
    delete_configuration_folders, 
    delete_study_folders,
    cleanup_all_empty_folders
)

# V-- Define the Blueprint --V
api_bp = Blueprint('api', __name__, url_prefix='/api')

# --- API Endpoints ---

@api_bp.route('/studies', methods=['GET', 'POST'])
def studies():
    """API Endpoint: Get list of studies or create a new study."""
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({"error": "Study 'name' is required"}), 400
        study_name = data['name'].strip()
        if not study_name:
            return jsonify({"error": "Study 'name' cannot be empty"}), 400

        # Get analyst name from request data
        analyst_name = data.get('analyst_name', '').strip() if data.get('analyst_name') else ''

        if Study.query.filter_by(name=study_name).first():
            return jsonify({"error": f"Study name '{study_name}' already exists"}), 409
        try:
            new_study = Study(name=study_name, analyst_name=analyst_name)
            db.session.add(new_study)
            db.session.commit()
            logging.info(f"API: Created study '{study_name}' with ID {new_study.id} by analyst '{analyst_name}'")
            return jsonify({
                "message": "Study created",
                "study_id": new_study.id,
                "name": new_study.name,
                "analyst_name": new_study.analyst_name,
                "created_at": new_study.created_at.isoformat() if new_study.created_at else None
            }), 201
        except Exception as e:
            db.session.rollback()
            logging.exception(f"API: Error creating study '{study_name}'")
            return jsonify({"error": f"Database error: {e}"}), 500
    else: # GET
        try:
            # Order by created_at in descending order (newest first)
            studies = Study.query.order_by(Study.created_at.desc()).all()
            return jsonify([{
                "id": s.id,
                "name": s.name,
                "analyst_name": s.analyst_name,
                "created_at": s.created_at.isoformat() if s.created_at else None
            } for s in studies])
        except Exception as e:
            logging.exception(f"API: Error fetching studies")
            return jsonify({"error": f"Database error: {e}"}), 500

@api_bp.route('/studies/<int:study_id>/configurations', methods=['GET'])
def get_configurations(study_id):
    """API Endpoint: Get list of configurations for a specific study."""
    study = db.session.get(Study, study_id)
    if not study:
        return jsonify({"error": f"Study {study_id} not found."}), 404
    try:
        # Keep configurations in descending order to show newest configurations first
        configurations = Configuration.query.filter_by(study_id=study_id).order_by(Configuration.id.desc()).all()
        config_list = [{
                "id": c.id,
                "name": c.name,
                "phases_n": c.phases_n,
                "include_bg_dist": c.include_bg_dist,
                "include_bg_assign": c.include_bg_assign,
                "include_trip_dist": c.include_trip_dist,
                "trip_dist_count": c.trip_dist_count,
                "include_trip_assign": c.include_trip_assign,
                "created_at": c.created_at.isoformat() if c.created_at else None
            } for c in configurations]
        return jsonify(config_list)
    except Exception as e:
        logging.exception(f"API: Error fetching configurations for study {study_id}")
        return jsonify({"error": f"Database error: {e}"}), 500

@api_bp.route('/studies/<int:study_id>/configure', methods=['POST'])
def configure_study(study_id):
    """API Endpoint: Configure scenarios for a specific study."""
    study = db.session.get(Study, study_id)
    if not study:
        return jsonify({"error": f"Study {study_id} not found."}), 404

    data = request.get_json()
    if not data or 'phases_n' not in data or 'config_name' not in data:
        return jsonify({"error": "'phases_n' and 'config_name' required"}), 400
    try:
        n = int(data['phases_n'])
        assert n >= 0
    except (ValueError, AssertionError):
        return jsonify({"error": "Invalid 'phases_n', must be a non-negative integer."}), 400

    config_name = data['config_name'].strip()
    if not config_name:
        return jsonify({"error": "'config_name' cannot be empty"}), 400

    # Check if configuration name already exists for this study
    existing_config = Configuration.query.filter_by(study_id=study_id, name=config_name).first()
    if existing_config:
        return jsonify({"error": f"Configuration name '{config_name}' already exists for this study"}), 400

    def get_b(p): return data.get(p, False) is True
    incl = {k: get_b(k) for k in ['include_bg_dist', 'include_bg_assign', 'include_trip_dist', 'include_trip_assign']}

    # Get trip distribution count if trip distribution is included
    trip_dist_count = 1
    if incl['include_trip_dist'] and 'trip_dist_count' in data:
        try:
            trip_dist_count = int(data['trip_dist_count'])
            if trip_dist_count < 1:
                trip_dist_count = 1
        except (ValueError, TypeError):
            trip_dist_count = 1

    try:
        # Create a new configuration
        new_config = Configuration(
            study_id=study_id,
            name=config_name,
            phases_n=n,
            include_bg_dist=incl['include_bg_dist'],
            include_bg_assign=incl['include_bg_assign'],
            include_trip_dist=incl['include_trip_dist'],
            trip_dist_count=trip_dist_count,
            include_trip_assign=incl['include_trip_assign']
        )
        db.session.add(new_config)
        db.session.flush()  # Get the new configuration ID

        # Create scenarios for this configuration
        scenarios_to_add = [Scenario(study_id=study.id, configuration_id=new_config.id, name='Existing', status=ProcessingStatus.PENDING_FILES)]
        for i in range(1, n + 1):
            scenarios_to_add.append(Scenario(study_id=study.id, configuration_id=new_config.id, name=f'No_Build_Phase_{i}', status=ProcessingStatus.PENDING_FILES))
            scenarios_to_add.append(Scenario(study_id=study.id, configuration_id=new_config.id, name=f'Build_Phase_{i}', status=ProcessingStatus.PENDING_FILES))
            if incl['include_bg_dist']: scenarios_to_add.append(Scenario(study_id=study.id, configuration_id=new_config.id, name=f'Background_Development_Distribution_Phase_{i}', status=ProcessingStatus.PENDING_FILES))
            if incl['include_bg_assign']: scenarios_to_add.append(Scenario(study_id=study.id, configuration_id=new_config.id, name=f'Background_Development_Assignment_Phase_{i}', status=ProcessingStatus.PENDING_FILES))

            # Create multiple trip distribution scenarios if needed
            if incl['include_trip_dist']:
                for j in range(1, trip_dist_count + 1):
                    # If there's only one trip distribution, don't add a number suffix
                    if trip_dist_count == 1:
                        scenarios_to_add.append(Scenario(study_id=study.id, configuration_id=new_config.id, name=f'Trip_Distribution_Phase_{i}', status=ProcessingStatus.PENDING_FILES))
                    else:
                        scenarios_to_add.append(Scenario(study_id=study.id, configuration_id=new_config.id, name=f'Trip_Distribution_{j}_Phase_{i}', status=ProcessingStatus.PENDING_FILES))

            if incl['include_trip_assign']: scenarios_to_add.append(Scenario(study_id=study.id, configuration_id=new_config.id, name=f'Trip_Assignment_Phase_{i}', status=ProcessingStatus.PENDING_FILES))

        db.session.add_all(scenarios_to_add)
        db.session.commit()

        logging.info(f"API: Created configuration '{config_name}' for study {study_id} with {len(scenarios_to_add)} scenarios.")
        s_list = [{"id": s.id, "name": s.name, "status": s.status.name} for s in scenarios_to_add]
        return jsonify({
            "message": "Configuration created",
            "configuration": {
                "id": new_config.id,
                "name": new_config.name,
                "phases_n": new_config.phases_n,
                "include_bg_dist": new_config.include_bg_dist,
                "include_bg_assign": new_config.include_bg_assign,
                "include_trip_dist": new_config.include_trip_dist,
                "trip_dist_count": new_config.trip_dist_count,
                "include_trip_assign": new_config.include_trip_assign
            },
            "scenarios": s_list
        }), 200
    except Exception as e:
        db.session.rollback()
        logging.exception(f"API: Error creating configuration for study {study_id}")
        return jsonify({"error": f"Database error during configuration: {e}"}), 500

@api_bp.route('/studies/<int:study_id>/scenarios', methods=['GET'])
def get_scenarios(study_id):
    """API Endpoint: Get list of scenarios for a specific study."""
    study = db.session.get(Study, study_id)
    if not study:
        return jsonify({"error": f"Study {study_id} not found."}), 404

    # Get configuration_id from query parameters if provided
    configuration_id = request.args.get('configuration_id', type=int)

    try:
        query = Scenario.query.filter_by(study_id=study_id)

        # Filter by configuration_id if provided
        if configuration_id:
            query = query.filter_by(configuration_id=configuration_id)

        # Order by ID in ascending order
        scenarios = query.order_by(Scenario.id.asc()).all()
        scenario_list = [{
                "id": s.id,
                "name": s.name,
                "status": s.status.name,
                "status_message": s.status_message,
                "configuration_id": s.configuration_id,
                "has_am_csv": bool(s.am_csv_path),
                "has_pm_csv": bool(s.pm_csv_path),
                "has_attout": bool(s.attout_txt_path),
                "has_merged": bool(s.merged_csv_path),
                "has_attin": bool(s.attin_txt_path)
            } for s in scenarios]
        return jsonify(scenario_list)
    except Exception as e:
        logging.exception(f"API: Error fetching scenarios for study {study_id}")
        return jsonify({"error": f"Database error: {e}"}), 500


@api_bp.route('/studies/<int:study_id>/scenarios/<int:scenario_id>/upload', methods=['POST'])
def upload_scenario_file(study_id, scenario_id):
    """API Endpoint: Upload AM CSV, PM CSV, or ATTOUT TXT file."""
    scenario = Scenario.query.filter_by(id=scenario_id, study_id=study_id).first()
    if not scenario:
        return jsonify({"error": f"Scenario {scenario_id} not found for study {study_id}."}), 404
    if scenario.status in [ProcessingStatus.PROCESSING]:
        return jsonify({"error": "Cannot upload file while processing is in progress."}), 409 # Conflict

    file_type = request.form.get('file_type')
    allowed_types = ['am_csv', 'pm_csv', 'attout_txt']
    if not file_type or file_type not in allowed_types:
        return jsonify({"error": f"Invalid 'file_type' (must be one of: {', '.join(allowed_types)})"}), 400

    if 'file' not in request.files:
        return jsonify({"error": "No 'file' part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Validate file extension
    is_valid, error_message = validate_file_extension(file, file_type)
    if not is_valid:
        return jsonify({"error": error_message}), 400

    # --- BEGIN MODIFICATION: Delete existing file if it exists ---
    existing_file_path_relative = None
    if file_type == 'am_csv' and scenario.am_csv_path:
        existing_file_path_relative = scenario.am_csv_path
        scenario.am_csv_path = None # Clear DB path before attempting delete/new upload
    elif file_type == 'pm_csv' and scenario.pm_csv_path:
        existing_file_path_relative = scenario.pm_csv_path
        scenario.pm_csv_path = None
    elif file_type == 'attout_txt' and scenario.attout_txt_path:
        existing_file_path_relative = scenario.attout_txt_path
        scenario.attout_txt_path = None
    
    if existing_file_path_relative:
        try:
            existing_file_path_absolute = get_absolute_path(existing_file_path_relative)
            if os.path.exists(existing_file_path_absolute):
                os.remove(existing_file_path_absolute)
                logging.info(f"API: Deleted existing file '{existing_file_path_absolute}' for scenario {scenario_id}, type {file_type}.")
            else:
                logging.warning(f"API: Existing file path '{existing_file_path_relative}' found in DB for scenario {scenario_id} (type {file_type}), but file not found at '{existing_file_path_absolute}'.")
        except Exception as e:
            # Log the error but proceed with uploading the new file.
            # The old path in DB is already cleared.
            logging.error(f"API: Error deleting existing file '{existing_file_path_relative}' for scenario {scenario_id}: {e}")
    # --- END MODIFICATION ---

    try:
        # Save the file and get the relative path
        original_filename = secure_filename(file.filename) # Get the original filename securely

        relative_save_path, filename = save_uploaded_file(file, study_id, scenario_id, file_type)
        logging.info(f"API: Saved file '{filename}' (original: '{original_filename}') for scenario {scenario_id} (type: {file_type}) to {relative_save_path}")

        # Update DB path AND original name for the specific file type
        if file_type == 'am_csv': 
            scenario.am_csv_path = relative_save_path
            scenario.am_csv_original_name = original_filename
        elif file_type == 'pm_csv': 
            scenario.pm_csv_path = relative_save_path
            scenario.pm_csv_original_name = original_filename
        elif file_type == 'attout_txt': 
            scenario.attout_txt_path = relative_save_path
            scenario.attout_txt_original_name = original_filename

        # Update status based on whether all required files are now present
        all_files_present = all([scenario.am_csv_path, scenario.pm_csv_path, scenario.attout_txt_path])

        if all_files_present:
            # Only change status to READY if it's currently PENDING or was previously COMPLETE/ERROR
            # Don't change if it's currently PROCESSING.
            if scenario.status in [ProcessingStatus.PENDING_CONFIG, ProcessingStatus.PENDING_FILES,
                                   ProcessingStatus.COMPLETE, ProcessingStatus.ERROR]:
                scenario.status = ProcessingStatus.READY_TO_PROCESS
                scenario.status_message = "All input files uploaded. Ready to process."
        else:
             # If not all files are present, revert to PENDING_FILES, unless there's an error
             if scenario.status != ProcessingStatus.ERROR:
                 scenario.status = ProcessingStatus.PENDING_FILES
                 scenario.status_message = "Waiting for other input file(s)."

        db.session.commit()
        return jsonify({
            "message": f"File '{secure_filename(file.filename)}' uploaded successfully for type '{file_type}'.",
            "saved_filename": filename,
            "scenario_status": scenario.status.name
        }), 200
    except Exception as e:
        db.session.rollback()
        logging.exception(f"API: Error saving file or updating DB for scenario {scenario_id}")
        # Note: The save_uploaded_file function handles the actual file saving
        return jsonify({"error": f"Could not save file or update database: {e}"}), 500


@api_bp.route('/studies/<int:study_id>/scenarios/<int:scenario_id>/process', methods=['POST'])
def process_scenario(study_id, scenario_id):
    """API Endpoint: Trigger processing to generate Merged CSV and ATTIN TXT."""
    scenario = Scenario.query.filter_by(id=scenario_id, study_id=study_id).first()
    if not scenario:
        return jsonify({"error": f"Scenario {scenario_id} not found for study {study_id}."}), 404

    # Allow reprocessing from ERROR or COMPLETE state too
    allowed_start_states = [ProcessingStatus.READY_TO_PROCESS, ProcessingStatus.ERROR, ProcessingStatus.COMPLETE]
    if scenario.status not in allowed_start_states:
        return jsonify({"error": f"Scenario not ready for processing. Current status: {scenario.status.name}. Must be READY, ERROR, or COMPLETE."}), 409 # Conflict or Bad State

    # Double-check required files are linked in DB
    required_paths_in_db = [scenario.am_csv_path, scenario.pm_csv_path, scenario.attout_txt_path]
    if not all(required_paths_in_db):
         # If somehow status is READY/COMPLETE/ERROR but paths are missing, update status
         if scenario.status != ProcessingStatus.ERROR:
            scenario.status = ProcessingStatus.PENDING_FILES
            scenario.status_message = "Missing required file paths in database record."
            try: db.session.commit()
            except Exception: db.session.rollback(); logging.error("Failed to update status to PENDING_FILES")
         return jsonify({"error": "Cannot process: Missing required file paths in database (AM CSV, PM CSV, ATTOUT TXT)."}), 400

    # Construct absolute paths and verify files exist on disk
    try:
        am_path = get_absolute_path(scenario.am_csv_path)
        pm_path = get_absolute_path(scenario.pm_csv_path)
        attout_path = get_absolute_path(scenario.attout_txt_path)
        output_dir_path = get_scenario_folder_path(study_id, scenario_id, folder_type="outputs")

        # Verify actual files exist
        if not os.path.exists(am_path): raise FileNotFoundError(f"AM file missing on disk: {scenario.am_csv_path}")
        if not os.path.exists(pm_path): raise FileNotFoundError(f"PM file missing on disk: {scenario.pm_csv_path}")
        if not os.path.exists(attout_path): raise FileNotFoundError(f"ATTOUT file missing on disk: {scenario.attout_txt_path}")

    except FileNotFoundError as fnf_e:
         logging.error(f"API: Required file not found on disk for scenario {scenario_id}: {fnf_e}")
         if scenario.status != ProcessingStatus.ERROR: # Update status only if not already Error
             scenario.status = ProcessingStatus.ERROR
             scenario.status_message = f"File not found on disk: {os.path.basename(str(fnf_e).split(': ')[-1])}"
             try: db.session.commit()
             except Exception: db.session.rollback(); logging.error("Failed to update status to ERROR for missing file")
         return jsonify({"error": f"File missing: {fnf_e}"}), 400 # Bad request as prerequisite missing
    except ValueError as path_e: # Error from get_scenario_folder_path
         logging.error(f"API: Error resolving output path for scenario {scenario_id}: {path_e}")
         if scenario.status != ProcessingStatus.ERROR:
             scenario.status = ProcessingStatus.ERROR
             scenario.status_message = f"Path error: {str(path_e)}"
             try: db.session.commit()
             except Exception: db.session.rollback(); logging.error("Failed to update status to ERROR for path issue")
         return jsonify({"error": f"Internal path configuration error: {str(path_e)}"}), 500
    except Exception as e: # Catch any other unexpected error during path setup
         logging.exception(f"API: Unexpected error setting up paths for scenario {scenario_id}: {e}")
         if scenario.status != ProcessingStatus.ERROR:
             scenario.status = ProcessingStatus.ERROR
             scenario.status_message = f"Unexpected path setup error: {str(e)}"
             try: db.session.commit()
             except Exception: db.session.rollback(); logging.error("Failed to update status to ERROR for path setup")
         return jsonify({"error": f"Unexpected path setup error: {e}"}), 500


    # --- Start Processing ---
    scenario.status = ProcessingStatus.PROCESSING
    scenario.status_message = "Processing started..."
    # Clear previous output paths immediately
    scenario.merged_csv_path = None
    scenario.attin_txt_path = None
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.exception(f"API: Failed to update status to PROCESSING for scenario {scenario_id}")
        # Re-fetch scenario in case commit failed but object changed
        scenario = db.session.get(Scenario, scenario_id)
        if scenario and scenario.status != ProcessingStatus.ERROR:
             scenario.status = ProcessingStatus.ERROR # Mark as error if we can't even start
             scenario.status_message = "Failed to set PROCESSING status in DB."
             try: db.session.commit()
             except Exception: db.session.rollback()
        return jsonify({"error": f"Database error before processing start: {e}"}), 500


    # --- Execute Core Logic ---
    try:
        merged_path_abs, attin_path_abs = process_traffic_data(
            am_path, pm_path, attout_path, output_dir_path, scenario.name
        )

        # --- Success ---
        # Convert absolute output paths back to relative for DB storage
        scenario.merged_csv_path = get_relative_path(merged_path_abs)
        scenario.attin_txt_path = get_relative_path(attin_path_abs)
        scenario.status = ProcessingStatus.COMPLETE
        scenario.status_message = "Processing completed successfully."
        db.session.commit() # Commit success state and paths
        logging.info(f"API: Successfully processed scenario {scenario_id} (Study {study_id})")
        return jsonify({
            "message": "Scenario processing completed successfully.",
            "scenario_id": scenario.id,
            "status": scenario.status.name,
            "merged_csv_path": scenario.merged_csv_path,
            "attin_txt_path": scenario.attin_txt_path
        }), 200

    except Exception as e:
        # --- Failure ---
        db.session.rollback() # Rollback any partial changes from the 'try' block
        # Re-fetch the scenario object within this exception handler's session context
        scenario = db.session.get(Scenario, scenario_id)
        if scenario: # Check if scenario still exists
            scenario.status = ProcessingStatus.ERROR
            # Be careful about error message length for status_message column
            error_msg = f"Processing failed: {str(e)}"
            scenario.status_message = (error_msg[:250] + '...') if len(error_msg) > 253 else error_msg
            # Ensure output paths are cleared on error
            scenario.merged_csv_path = None
            scenario.attin_txt_path = None
            try:
                db.session.commit() # Commit the error state
            except Exception as commit_e:
                db.session.rollback()
                logging.error(f"API: CRITICAL - Failed to commit ERROR status for scenario {scenario_id} after processing failure. DB error: {commit_e}")
        else:
            logging.error(f"API: Scenario {scenario_id} was not found when trying to record processing error.")

        logging.exception(f"API: Processing failed for scenario {scenario_id} (Study {study_id})")
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500 # Internal Server Error


@api_bp.route('/studies/<int:study_id>/scenarios/<int:scenario_id>/status', methods=['GET'])
def get_scenario_status(study_id, scenario_id):
    """API Endpoint: Get the current status and file presence for a scenario."""
    scenario = Scenario.query.filter_by(id=scenario_id, study_id=study_id).first()
    if not scenario:
        return jsonify({"error": f"Scenario {scenario_id} not found for study {study_id}."}), 404
    try:
        uploaded_files_info = [
            {
                "file_type_id": "am_csv",
                "file_type_label": "AM CSV",
                "original_name": scenario.am_csv_original_name,
                "is_uploaded": bool(scenario.am_csv_path)
            },
            {
                "file_type_id": "pm_csv",
                "file_type_label": "PM CSV",
                "original_name": scenario.pm_csv_original_name,
                "is_uploaded": bool(scenario.pm_csv_path)
            },
            {
                "file_type_id": "attout_txt",
                "file_type_label": "ATTOUT TXT",
                "original_name": scenario.attout_txt_original_name,
                "is_uploaded": bool(scenario.attout_txt_path)
            }
        ]

        # Get configuration name
        config = db.session.get(Configuration, scenario.configuration_id)
        config_name = config.name if config else "Unknown Configuration"
        
        return jsonify({
            "id": scenario.id,
            "configuration_id": scenario.configuration_id,
            "configuration_name": config_name,
            "name": scenario.name,
            "status": scenario.status.name,
            "status_message": scenario.status_message,
            "uploaded_files": uploaded_files_info, # New list with detailed file info
            # Keep these for any part of the frontend still using them directly, though the new list is preferred
            "has_am_csv": bool(scenario.am_csv_path),
            "has_pm_csv": bool(scenario.pm_csv_path),
            "has_attout": bool(scenario.attout_txt_path),
            "has_merged": bool(scenario.merged_csv_path),
            "has_attin": bool(scenario.attin_txt_path)
        })
    except Exception as e:
        logging.exception(f"API: Error fetching status for scenario {scenario_id}")
        return jsonify({"error": f"Error retrieving scenario status: {e}"}), 500


@api_bp.route('/studies/<int:study_id>/scenarios/<int:scenario_id>/download/<file_type>', methods=['GET'])
def download_scenario_file(study_id, scenario_id, file_type):
    """API Endpoint: Download generated output files or original uploaded files."""
    scenario = Scenario.query.filter_by(id=scenario_id, study_id=study_id).first()
    if not scenario:
        abort(404, description=f"Scenario {scenario_id} not found for study {study_id}.")

    # Get download information using the utility function
    file_path_relative, download_name_default, is_upload_file = get_download_info(scenario, file_type)

    if file_path_relative is None:
        allowed_downloads = ['merged', 'am_csv', 'pm_csv', 'attout_txt', 'attin_txt']
        abort(404, description=f"Invalid file type '{file_type}'. Allowed types: {', '.join(allowed_downloads)}")

    if not file_path_relative:
        logging.warning(f"API: Download requested for '{file_type}' but path is missing in DB for scenario {scenario_id}.")
        abort(404, description=f"File path for type '{file_type}' not found in database record for this scenario.")

    # Construct absolute path
    file_path_absolute = get_absolute_path(file_path_relative)

    # Security check: Ensure the resolved path is still within the intended base directory (uploads or outputs)
    # This helps prevent directory traversal attacks (e.g., if file_path_relative somehow contains '../..')
    upload_dir_abs = os.path.normpath(current_app.config['UPLOAD_FOLDER'])
    output_dir_abs = os.path.normpath(current_app.config['OUTPUT_FOLDER'])
    if not (file_path_absolute.startswith(upload_dir_abs) or file_path_absolute.startswith(output_dir_abs)):
         logging.error(f"API: SECURITY - Attempt to access file outside allowed directories: {file_path_absolute}")
         abort(403, description="Access denied to the requested file path.") # Forbidden

    # Determine the final download name
    download_name = download_name_default # Start with the default
    if is_upload_file:
        # Try to extract the original filename stored after the prefix (e.g., 'am_csv_original_name.csv')
        base_filename = os.path.basename(file_path_absolute)
        prefix = f"{file_type}_"
        if base_filename.startswith(prefix):
             original_part = base_filename[len(prefix):]
             if original_part: # Ensure it's not empty
                download_name = original_part # Use the extracted name
             else:
                 logging.warning(f"API: Found prefix '{prefix}' but original filename part is empty for {file_path_absolute}. Using default.")
        else:
            # If the prefix isn't there (maybe older data?), use the whole basename but log a warning.
            logging.warning(f"API: Expected prefix '{prefix}' not found in upload filename {file_path_absolute}. Using full basename as download name.")
            download_name = base_filename

    # Check if the file actually exists on the filesystem
    if not os.path.exists(file_path_absolute):
         logging.error(f"API: File missing from disk: {file_path_absolute} (DB Path: {file_path_relative})")
         abort(404, description=f"File '{download_name}' is registered but missing from the server filesystem.")

    # Use send_from_directory for security and proper header handling
    directory = os.path.dirname(file_path_absolute)
    filename = os.path.basename(file_path_absolute)
    logging.info(f"API: Serving file download '{filename}' from directory '{directory}' with download name '{download_name}'")
    try:
        return send_from_directory(directory, filename, as_attachment=True, download_name=download_name)
    except Exception as e:
        # Catch potential errors from send_from_directory (e.g., file read issues)
        logging.exception(f"API: Error sending file '{filename}' using send_from_directory: {e}")
        abort(500, description="Server error occurred while trying to send the file.")

@api_bp.route('/studies/<int:study_id>/configurations/<int:config_id>', methods=['DELETE'])
def delete_configuration(study_id, config_id):
    """API Endpoint: Delete a configuration and its associated scenarios."""
    study = db.session.get(Study, study_id)
    if not study:
        return jsonify({"error": f"Study {study_id} not found."}), 404

    config = db.session.get(Configuration, config_id)
    if not config or config.study_id != study_id:
        return jsonify({"error": f"Configuration {config_id} not found for study {study_id}."}), 404

    try:
        # First, delete all scenarios associated with this configuration
        scenarios = Scenario.query.filter_by(configuration_id=config_id).all()
        
        # Track deleted files
        total_uploads_deleted = 0
        total_outputs_deleted = 0
        total_uploads_folders_deleted = 0
        total_outputs_folders_deleted = 0
        
        # Delete files and folders for each scenario
        for scenario in scenarios:
            # Delete files
            uploads_deleted, outputs_deleted = delete_scenario_files(scenario)
            total_uploads_deleted += uploads_deleted
            total_outputs_deleted += outputs_deleted
            
            # Delete folders
            folders_uploads_deleted, folders_outputs_deleted = delete_scenario_folders(study_id, scenario.id)
            if folders_uploads_deleted:
                total_uploads_folders_deleted += 1
            if folders_outputs_deleted:
                total_outputs_folders_deleted += 1
                
            # Delete scenario from database
            db.session.delete(scenario)
        
        # Delete configuration folders
        config_uploads_deleted, config_outputs_deleted = delete_configuration_folders(study_id, config_id)

        # Then delete the configuration itself
        db.session.delete(config)
        db.session.commit()
        
        # Clean up any empty folders left behind
        empty_uploads_removed, empty_outputs_removed = cleanup_all_empty_folders()

        logging.info(f"API: Deleted configuration {config_id} with {len(scenarios)} associated scenarios from study {study_id}")
        logging.info(f"API: Deleted {total_uploads_deleted} upload files and {total_outputs_deleted} output files")
        logging.info(f"API: Deleted {total_uploads_folders_deleted} scenario upload folders and {total_outputs_folders_deleted} scenario output folders")
        logging.info(f"API: Deleted configuration folders: uploads={config_uploads_deleted}, outputs={config_outputs_deleted}")
        logging.info(f"API: Cleaned up {empty_uploads_removed} empty upload folders and {empty_outputs_removed} empty output folders")
        
        return jsonify({
            "message": f"Configuration '{config.name}' and {len(scenarios)} associated scenarios deleted successfully.",
            "files_deleted": {
                "uploads": total_uploads_deleted,
                "outputs": total_outputs_deleted,
                "scenario_folders": total_uploads_folders_deleted + total_outputs_folders_deleted,
                "config_folders_deleted": config_uploads_deleted or config_outputs_deleted,
                "empty_folders_removed": empty_uploads_removed + empty_outputs_removed
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        logging.exception(f"API: Error deleting configuration {config_id} from study {study_id}")
        return jsonify({"error": f"Database error during deletion: {e}"}), 500

@api_bp.route('/studies/<int:study_id>/scenarios/<int:scenario_id>', methods=['DELETE'])
def delete_scenario(study_id, scenario_id):
    """API Endpoint: Delete a specific scenario."""
    study = db.session.get(Study, study_id)
    if not study:
        return jsonify({"error": f"Study {study_id} not found."}), 404

    scenario = db.session.get(Scenario, scenario_id)
    if not scenario or scenario.study_id != study_id:
        return jsonify({"error": f"Scenario {scenario_id} not found for study {study_id}."}), 404

    # Get the configuration ID before deleting the scenario
    configuration_id = scenario.configuration_id
    scenario_name = scenario.name

    try:
        # First, delete the files
        # Delete individual files (helpful for old-style paths)
        uploads_deleted, outputs_deleted = delete_scenario_files(scenario)
        
        # Delete scenario folders
        folders_uploads_deleted, folders_outputs_deleted = delete_scenario_folders(study_id, scenario_id)
        
        # Now delete the database record
        db.session.delete(scenario)
        db.session.commit()

        # Clean up any empty folders left behind
        empty_uploads_removed, empty_outputs_removed = cleanup_all_empty_folders()

        logging.info(f"API: Deleted scenario {scenario_id} ('{scenario_name}') from study {study_id}")
        logging.info(f"API: Deleted {uploads_deleted} upload files and {outputs_deleted} output files")
        logging.info(f"API: Deleted scenario folders: uploads={folders_uploads_deleted}, outputs={folders_outputs_deleted}")
        logging.info(f"API: Cleaned up {empty_uploads_removed} empty upload folders and {empty_outputs_removed} empty output folders")
        
        return jsonify({
            "message": f"Scenario '{scenario_name}' deleted successfully.",
            "configuration_id": configuration_id,
            "files_deleted": {
                "uploads": uploads_deleted,
                "outputs": outputs_deleted,
                "uploads_folder": folders_uploads_deleted,
                "outputs_folder": folders_outputs_deleted,
                "empty_folders_removed": empty_uploads_removed + empty_outputs_removed
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        logging.exception(f"API: Error deleting scenario {scenario_id} from study {study_id}")
        return jsonify({"error": f"Database error during deletion: {e}"}), 500

@api_bp.route('/studies/<int:study_id>', methods=['DELETE'])
def delete_study(study_id):
    """API Endpoint: Delete a study and all its associated data (configurations, scenarios, uploads, outputs)."""
    study = db.session.get(Study, study_id)
    if not study:
        return jsonify({"error": f"Study {study_id} not found."}), 404

    try:
        # Track deletion statistics
        total_configs = 0
        total_scenarios = 0
        total_uploads_deleted = 0
        total_outputs_deleted = 0
        configs_deleted = []
        
        # Get all configurations for this study
        configurations = Configuration.query.filter_by(study_id=study_id).all()
        total_configs = len(configurations)

        # Process each configuration
        for config in configurations:
            config_id = config.id
            configs_deleted.append(config_id)
            
            # Get all scenarios for this configuration
            scenarios = Scenario.query.filter_by(configuration_id=config_id).all()
            total_scenarios += len(scenarios)
            
            # Delete each scenario's files
            for scenario in scenarios:
                # Delete individual files
                uploads_deleted, outputs_deleted = delete_scenario_files(scenario)
                total_uploads_deleted += uploads_deleted
                total_outputs_deleted += outputs_deleted
                
                # Delete scenario folders
                delete_scenario_folders(study_id, scenario.id)
                
                # Now delete the scenario from DB
                db.session.delete(scenario)
            
            # Delete configuration folder
            delete_configuration_folders(study_id, config_id)
            
            # Delete configuration from DB
            db.session.delete(config)
        
        # Delete study folders
        study_uploads_deleted, study_outputs_deleted = delete_study_folders(study_id)
        
        # Finally, delete the study itself
        study_name = study.name
        db.session.delete(study)
        db.session.commit()
        
        # Clean up any empty folders left behind
        empty_uploads_removed, empty_outputs_removed = cleanup_all_empty_folders()

        logging.info(f"API: Deleted study {study_id} ('{study_name}') with {total_configs} configurations and {total_scenarios} scenarios")
        logging.info(f"API: Deleted {total_uploads_deleted} upload files and {total_outputs_deleted} output files")
        logging.info(f"API: Deleted study folders: uploads={study_uploads_deleted}, outputs={study_outputs_deleted}")
        logging.info(f"API: Cleaned up {empty_uploads_removed} empty upload folders and {empty_outputs_removed} empty output folders")
        
        return jsonify({
            "message": f"Study '{study_name}' deleted successfully with {total_configs} configurations and {total_scenarios} scenarios.",
            "files_deleted": {
                "uploads": total_uploads_deleted,
                "outputs": total_outputs_deleted,
                "study_folders_deleted": study_uploads_deleted or study_outputs_deleted,
                "configurations_deleted": configs_deleted,
                "empty_folders_removed": empty_uploads_removed + empty_outputs_removed
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        logging.exception(f"API: Error deleting study {study_id}")
        return jsonify({"error": f"Database error during deletion: {e}"}), 500

@api_bp.route('/studies/<int:study_id>/scenarios/<int:scenario_id>/files/<string:file_type_id>', methods=['DELETE'])
def delete_scenario_file_typed(study_id, scenario_id, file_type_id):
    """API Endpoint: Delete a specific uploaded file (AM, PM, ATTOUT) for a scenario."""
    logging.info(f"API: Request to delete file_type '{file_type_id}' for scenario {scenario_id}, study {study_id}")
    scenario = Scenario.query.filter_by(id=scenario_id, study_id=study_id).first()
    if not scenario:
        return jsonify({"error": f"Scenario {scenario_id} not found for study {study_id}."}), 404

    if scenario.status == ProcessingStatus.PROCESSING:
        return jsonify({"error": "Cannot delete files while scenario is processing."}), 409 # Conflict

    valid_file_types = {
        'am_csv': ('am_csv_path', 'am_csv_original_name'),
        'pm_csv': ('pm_csv_path', 'pm_csv_original_name'),
        'attout_txt': ('attout_txt_path', 'attout_txt_original_name')
    }

    if file_type_id not in valid_file_types:
        return jsonify({"error": f"Invalid file_type_id '{file_type_id}'. Allowed types: {list(valid_file_types.keys())}"}), 400

    path_attr, name_attr = valid_file_types[file_type_id]
    file_path_relative = getattr(scenario, path_attr, None)

    if not file_path_relative:
        logging.warning(f"API: No file of type '{file_type_id}' found in DB for scenario {scenario_id} to delete.")
        # Still return success and current state, as the desired state (file gone) is met.
    else:
        try:
            file_path_absolute = get_absolute_path(file_path_relative)
            if os.path.exists(file_path_absolute):
                os.remove(file_path_absolute)
                logging.info(f"API: Successfully deleted physical file: {file_path_absolute}")
            else:
                logging.warning(f"API: DB path '{file_path_relative}' existed for {file_type_id} of scenario {scenario_id}, but file not on disk at '{file_path_absolute}'.")
            
            # Clear DB fields for this file type
            setattr(scenario, path_attr, None)
            setattr(scenario, name_attr, None)
            logging.info(f"API: Cleared DB fields for {file_type_id} on scenario {scenario_id}.")

        except Exception as e:
            db.session.rollback() # Rollback if any error during file op or setattr
            logging.exception(f"API: Error during physical file deletion or DB clear for {file_type_id} of scenario {scenario_id}: {e}")
            return jsonify({"error": f"Error processing file deletion for {file_type_id}: {str(e)}"}), 500

    # Update scenario status - if it was READY, it might now be PENDING_FILES
    # Don't change if it's PENDING_CONFIG, PROCESSING, or already ERROR/COMPLETE (unless specific logic dictates)
    if not all([scenario.am_csv_path, scenario.pm_csv_path, scenario.attout_txt_path]):
        if scenario.status == ProcessingStatus.READY_TO_PROCESS or scenario.status == ProcessingStatus.COMPLETE:
            scenario.status = ProcessingStatus.PENDING_FILES
            scenario.status_message = "One or more required files are now missing after deletion."
            logging.info(f"API: Scenario {scenario_id} status updated to PENDING_FILES due to file deletion.")
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.exception(f"API: Database error committing changes after file deletion for scenario {scenario_id}: {e}")
        return jsonify({"error": f"Database error after file deletion: {str(e)}"}), 500

    # Return the updated scenario status, similar to get_scenario_status
    updated_uploaded_files_info = [
        {"file_type_id": "am_csv", "file_type_label": "AM CSV", "original_name": scenario.am_csv_original_name, "is_uploaded": bool(scenario.am_csv_path)},
        {"file_type_id": "pm_csv", "file_type_label": "PM CSV", "original_name": scenario.pm_csv_original_name, "is_uploaded": bool(scenario.pm_csv_path)},
        {"file_type_id": "attout_txt", "file_type_label": "ATTOUT TXT", "original_name": scenario.attout_txt_original_name, "is_uploaded": bool(scenario.attout_txt_path)}
    ]
    return jsonify({
        "message": f"File type '{file_type_id}' processed for deletion successfully.",
        "scenario_id": scenario.id,
        "name": scenario.name,
        "status": scenario.status.name,
        "status_message": scenario.status_message,
        "uploaded_files": updated_uploaded_files_info,
        "has_am_csv": bool(scenario.am_csv_path),
        "has_pm_csv": bool(scenario.pm_csv_path),
        "has_attout": bool(scenario.attout_txt_path),
        "has_merged": bool(scenario.merged_csv_path),
        "has_attin": bool(scenario.attin_txt_path)
    }), 200

# --- END OF traffic_app/routes/api.py ---