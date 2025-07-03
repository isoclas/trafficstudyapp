import os
import shutil
from flask import current_app
from werkzeug.utils import secure_filename

def allowed_file(filename):
    """Checks if the filename has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def get_scenario_folder_path(study_id, scenario_id, folder_type="uploads"):
    """Generates a structured path for scenario files and ensures it exists.
    
    Structure:
    uploads/outputs > study_id_study_name_analyst_name > configuration_id_configuration_name > scenario_name
    """
    if folder_type == "uploads":
        base_folder = current_app.config['UPLOAD_FOLDER']
    elif folder_type == "outputs":
        base_folder = current_app.config['OUTPUT_FOLDER']
    else:
        raise ValueError("Invalid folder_type specified")

    # Import here to avoid circular imports
    from .models import Study, Configuration, Scenario

    try:
        # Fetch the scenario, study and configuration information
        scenario = Scenario.query.get(scenario_id)
        if not scenario:
            # Fallback to simple path if scenario not found
            path = os.path.join(base_folder, str(study_id), str(scenario_id))
            os.makedirs(path, exist_ok=True)
            return path
            
        study = Study.query.get(study_id)
        config = Configuration.query.get(scenario.configuration_id)
        
        # Create a clean version of names for folder structure
        study_name = secure_filename(study.name) if study else "unknown_study"
        analyst_name = secure_filename(study.analyst_name) if study and study.analyst_name else "unknown_analyst"
        config_name = secure_filename(config.name) if config else "unknown_config"
        scenario_name = secure_filename(scenario.name)
        
        # Format path: base/study_id_name_analyst/config_id_name/scenario_name
        study_folder = f"{study_id}_{study_name}_{analyst_name}"
        config_folder = f"{scenario.configuration_id}_{config_name}"
        
        path = os.path.join(base_folder, study_folder, config_folder, scenario_name)
        os.makedirs(path, exist_ok=True)
        return path
        
    except Exception as e:
        # If any error occurs, log it and fallback to the simple path structure
        current_app.logger.error(f"Error creating folder structure: {e}")
    path = os.path.join(base_folder, str(study_id), str(scenario_id))
    os.makedirs(path, exist_ok=True)
    return path

def get_absolute_path(relative_path):
    """Convert a relative path to an absolute path based on the BASE_DIR.
    
    Works with both old-style and new-style paths.
    """
    if not relative_path:
        return None
        
    base_dir = current_app.config['BASE_DIR']
    return os.path.join(base_dir, relative_path)

def get_relative_path(absolute_path):
    """Convert an absolute path to a path relative to BASE_DIR.
    
    Works with both old-style and new-style paths.
    """
    if not absolute_path:
        return None
        
    base_dir = current_app.config['BASE_DIR']
    return os.path.relpath(absolute_path, base_dir)

def save_uploaded_file(file, study_id, scenario_id, file_type):
    """Save an uploaded file and return the relative path.

    Args:
        file: The file object from request.files
        study_id: The study ID
        scenario_id: The scenario ID
        file_type: Type of file ('am_csv', 'pm_csv', 'attout_txt')

    Returns:
        tuple: (relative_path, filename)
    """
    # Create a secure filename
    safe_original_filename = secure_filename(file.filename)
    # Prepend file type to avoid name collisions
    filename = f"{file_type}_{safe_original_filename}"

    # Get the upload directory using the enhanced function for nested structure
    upload_dir = get_scenario_folder_path(study_id, scenario_id, "uploads")

    # Full path to save the file
    save_path = os.path.join(upload_dir, filename)

    # Save the file
    file.save(save_path)

    # Return the path relative to BASE_DIR
    return get_relative_path(save_path), filename

def validate_file_extension(file, file_type):
    """Validate that the file has the correct extension for its type.

    Args:
        file: The file object from request.files
        file_type: Type of file ('am_csv', 'pm_csv', 'attout_txt')

    Returns:
        tuple: (is_valid, error_message)
    """
    expected_ext = 'csv' if file_type in ['am_csv', 'pm_csv'] else 'txt'
    actual_ext = ''

    if '.' in file.filename:
        actual_ext = file.filename.rsplit('.', 1)[1].lower()

    if actual_ext != expected_ext or actual_ext not in current_app.config['ALLOWED_EXTENSIONS']:
        allowed_exts_str = ", ".join(current_app.config['ALLOWED_EXTENSIONS'])
        error_msg = f"Invalid file extension for type '{file_type}'. Expected '.{expected_ext}'. Allowed types: {allowed_exts_str}"
        return False, error_msg

    return True, ""

def get_download_info(scenario, file_type):
    """Get download information for a file.

    Args:
        scenario: The Scenario object
        file_type: Type of file to download

    Returns:
        tuple: (relative_path, download_name, is_upload_file) or (None, None, None) if invalid
    """
    # Create a user-friendly filename based on the scenario name
    expected_filename_base = secure_filename(scenario.name)

    # Map file_type to the relative path attribute and default download name
    path_map = {
        'merged': (scenario.merged_csv_path, f"{expected_filename_base}_Merged.csv", False),
        'am_csv': (scenario.am_csv_path, 'AM_Data.csv', True),
        'pm_csv': (scenario.pm_csv_path, 'PM_Data.csv', True),
        'attout_txt': (scenario.attout_txt_path, 'ATTOUT_Data.txt', True),
        'attin_txt': (scenario.attin_txt_path, f"{expected_filename_base}_ATTIN.txt", False),
    }

    if file_type not in path_map:
        return None, None, None

    # Get the path and info
    rel_path, default_name, is_upload = path_map[file_type]
    
    # For uploaded files, try to extract original filename from the stored filename
    if is_upload and rel_path:
        try:
            filename = os.path.basename(rel_path)
            if filename.startswith(file_type + '_'):
                original_name = filename[len(file_type + '_'):]
                if original_name:  # If we successfully extracted a name
                    return rel_path, original_name, is_upload
        except:
            # If any error occurs, use the default approach
            pass
    
    return rel_path, default_name, is_upload

def delete_file_if_exists(file_path):
    """Delete a file if it exists.
    
    Args:
        file_path: Absolute path to the file to delete
        
    Returns:
        bool: True if file was deleted, False if it didn't exist
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        current_app.logger.error(f"Error deleting file '{file_path}': {str(e)}")
        return False

def delete_folder_if_exists(folder_path):
    """Delete a folder and all its contents if it exists.
    
    Args:
        folder_path: Absolute path to the folder to delete
        
    Returns:
        bool: True if folder was deleted, False if it didn't exist
    """
    try:
        if folder_path and os.path.exists(folder_path):
            shutil.rmtree(folder_path)
            return True
        return False
    except Exception as e:
        current_app.logger.error(f"Error deleting folder '{folder_path}': {str(e)}")
        return False

def delete_scenario_files(scenario, delete_uploads=True, delete_outputs=True):
    """Delete all files associated with a scenario.
    
    Args:
        scenario: Scenario object
        delete_uploads: Whether to delete uploaded files
        delete_outputs: Whether to delete output files
        
    Returns:
        tuple: (uploads_deleted, outputs_deleted) counts of deleted files
    """
    uploads_deleted = 0
    outputs_deleted = 0
    
    try:
        # Delete uploaded files if requested
        if delete_uploads:
            for file_attr in ['am_csv_path', 'pm_csv_path', 'attout_txt_path']:
                file_path = getattr(scenario, file_attr)
                if file_path:
                    abs_path = get_absolute_path(file_path)
                    if delete_file_if_exists(abs_path):
                        uploads_deleted += 1
        
        # Delete output files if requested
        if delete_outputs:
            for file_attr in ['merged_csv_path', 'attin_txt_path']:
                file_path = getattr(scenario, file_attr)
                if file_path:
                    abs_path = get_absolute_path(file_path)
                    if delete_file_if_exists(abs_path):
                        outputs_deleted += 1
    
    except Exception as e:
        current_app.logger.error(f"Error deleting scenario files: {str(e)}")
    
    return uploads_deleted, outputs_deleted

def delete_scenario_folders(study_id, scenario_id, delete_uploads=True, delete_outputs=True):
    """Delete the folders associated with a scenario.
    
    Args:
        study_id: Study ID
        scenario_id: Scenario ID
        delete_uploads: Whether to delete the uploads folder
        delete_outputs: Whether to delete the outputs folder
        
    Returns:
        tuple: (uploads_deleted, outputs_deleted) boolean indicating if folders were deleted
    """
    uploads_deleted = False
    outputs_deleted = False
    
    try:
        # Get folder paths using the folder structure function
        if delete_uploads:
            uploads_folder = get_scenario_folder_path(study_id, scenario_id, folder_type="uploads")
            uploads_deleted = delete_folder_if_exists(uploads_folder)
        
        if delete_outputs:
            outputs_folder = get_scenario_folder_path(study_id, scenario_id, folder_type="outputs")
            outputs_deleted = delete_folder_if_exists(outputs_folder)
    
    except Exception as e:
        current_app.logger.error(f"Error deleting scenario folders: {str(e)}")
    
    return uploads_deleted, outputs_deleted

def delete_configuration_folders(study_id, config_id, delete_uploads=True, delete_outputs=True):
    """Delete the configuration folders and all scenario folders within them.
    
    Args:
        study_id: Study ID
        config_id: Configuration ID
        delete_uploads: Whether to delete upload folders
        delete_outputs: Whether to delete output folders
        
    Returns:
        tuple: (uploads_deleted, outputs_deleted) boolean indicating if folders were deleted
    """
    uploads_deleted = False
    outputs_deleted = False
    
    try:
        from .models import Study, Configuration
        
        # Get the study and configuration to build the folder paths
        study = Study.query.get(study_id)
        config = Configuration.query.get(config_id)
        
        if not study or not config:
            current_app.logger.warning(f"Study {study_id} or Configuration {config_id} not found for folder deletion")
            return False, False
            
        # Create folder names
        study_name = secure_filename(study.name)
        analyst_name = secure_filename(study.analyst_name) if study.analyst_name else "unknown_analyst"
        config_name = secure_filename(config.name)
        
        study_folder = f"{study_id}_{study_name}_{analyst_name}"
        config_folder = f"{config_id}_{config_name}"
        
        # Delete folders
        if delete_uploads:
            base_folder = current_app.config['UPLOAD_FOLDER']
            config_path = os.path.join(base_folder, study_folder, config_folder)
            uploads_deleted = delete_folder_if_exists(config_path)
            
        if delete_outputs:
            base_folder = current_app.config['OUTPUT_FOLDER']
            config_path = os.path.join(base_folder, study_folder, config_folder)
            outputs_deleted = delete_folder_if_exists(config_path)
            
    except Exception as e:
        current_app.logger.error(f"Error deleting configuration folders: {str(e)}")
        
    return uploads_deleted, outputs_deleted

def delete_study_folders(study_id, delete_uploads=True, delete_outputs=True):
    """Delete the study folders and all configuration folders within them.
    
    Args:
        study_id: Study ID
        delete_uploads: Whether to delete upload folders
        delete_outputs: Whether to delete output folders
        
    Returns:
        tuple: (uploads_deleted, outputs_deleted) boolean indicating if folders were deleted
    """
    uploads_deleted = False
    outputs_deleted = False
    
    try:
        from .models import Study
        
        # Get the study to build the folder path
        study = Study.query.get(study_id)
        
        if not study:
            current_app.logger.warning(f"Study {study_id} not found for folder deletion")
            return False, False
            
        # Create folder name
        study_name = secure_filename(study.name)
        analyst_name = secure_filename(study.analyst_name) if study.analyst_name else "unknown_analyst"
        study_folder = f"{study_id}_{study_name}_{analyst_name}"
        
        # Delete folders
        if delete_uploads:
            base_folder = current_app.config['UPLOAD_FOLDER']
            study_path = os.path.join(base_folder, study_folder)
            uploads_deleted = delete_folder_if_exists(study_path)
            
        if delete_outputs:
            base_folder = current_app.config['OUTPUT_FOLDER']
            study_path = os.path.join(base_folder, study_folder)
            outputs_deleted = delete_folder_if_exists(study_path)
            
    except Exception as e:
        current_app.logger.error(f"Error deleting study folders: {str(e)}")
        
    return uploads_deleted, outputs_deleted

def cleanup_empty_folders(base_folder):
    """Recursively remove empty folders under the base folder.
    
    Args:
        base_folder: Path to the base folder to clean up
        
    Returns:
        int: Number of empty folders removed
    """
    if not os.path.exists(base_folder):
        return 0
        
    removed_count = 0
    
    try:
        # Walk the directory tree from bottom up
        for root, dirs, files in os.walk(base_folder, topdown=False):
            # Skip the base folder itself
            if root == base_folder:
                continue
                
            # If the directory is empty (no files and no non-empty dirs)
            if not files and not os.listdir(root):
                os.rmdir(root)
                removed_count += 1
                current_app.logger.info(f"Removed empty folder: {root}")
    except Exception as e:
        current_app.logger.error(f"Error cleaning up empty folders in {base_folder}: {str(e)}")
        
    return removed_count

def cleanup_all_empty_folders():
    """Clean up empty folders in both uploads and outputs directories.
    
    Returns:
        tuple: (uploads_count, outputs_count) number of empty folders removed
    """
    uploads_count = 0
    outputs_count = 0
    
    try:
        # Clean up uploads folder
        uploads_folder = current_app.config['UPLOAD_FOLDER']
        if os.path.exists(uploads_folder):
            uploads_count = cleanup_empty_folders(uploads_folder)
            
        # Clean up outputs folder
        outputs_folder = current_app.config['OUTPUT_FOLDER']
        if os.path.exists(outputs_folder):
            outputs_count = cleanup_empty_folders(outputs_folder)
    except Exception as e:
        current_app.logger.error(f"Error in cleanup_all_empty_folders: {str(e)}")
        
    return uploads_count, outputs_count