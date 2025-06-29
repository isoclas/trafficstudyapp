# --- START OF traffic_app/api_client.py ---
import logging
import os
import requests
from datetime import datetime
from flask import url_for, current_app
from typing import Dict, List, Any, Tuple, Optional, Union

# Import models and db for direct database access in production
try:
    from .models import Study, Configuration, Scenario, ProcessingStatus
    from .extensions import db
except ImportError:
    # Fallback for cases where models aren't available
    Study = Configuration = Scenario = ProcessingStatus = db = None

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO format date string to datetime object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception as e:
        logging.error(f"Error parsing date {date_str}: {e}")
        return None

def _process_dates_in_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process all date strings in a dictionary to datetime objects."""
    if 'created_at' in data and data['created_at']:
        data['created_at'] = _parse_date(data['created_at'])
    return data

def _process_dates_in_list(data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process all date strings in a list of dictionaries to datetime objects."""
    for item in data_list:
        _process_dates_in_dict(item)
    return data_list

def get_studies() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Get all studies from the API or database directly.
    
    Returns:
        Tuple[List[Dict], Optional[str]]: (studies list, error message if any)
    """
    studies = []
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Study is not None:
        try:
            # Direct database query instead of HTTP request
            study_objects = Study.query.order_by(Study.created_at.desc()).all()
            studies = []
            for s in study_objects:
                study_dict = {
                    "id": s.id,
                    "name": s.name,
                    "analyst_name": s.analyst_name,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "configurations_count": len(s.configurations),
                    "scenarios_count": len(s.scenarios),
                    "configurations": []
                }
                # Add full configuration and scenario data for status calculation
                for config in s.configurations:
                    config_dict = {
                        "id": config.id,
                        "name": config.name,
                        "scenarios": []
                    }
                    for scenario in config.scenarios:
                        scenario_dict = {
                            "id": scenario.id,
                            "name": scenario.name,
                            "status": {"value": scenario.status.value}
                        }
                        config_dict["scenarios"].append(scenario_dict)
                    study_dict["configurations"].append(config_dict)
                studies.append(study_dict)
        except Exception as e:
            error = f'Database error fetching studies: {e}'
            logging.error(f"API Client: Database error fetching studies: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.studies', _external=True)
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            studies = response.json()
            studies = _process_dates_in_list(studies)
        except requests.exceptions.RequestException as e:
            error = f'Error fetching studies from API: {e}'
            logging.error(f"API Client: Failed to fetch studies from API ({api_url}): {e}")
        except Exception as e:
            error = f'An unexpected error occurred fetching studies: {e}'
            logging.error(f"API Client: Unexpected error fetching studies: {e}")
    
    return studies, error

def create_study(name: str, analyst_name: str) -> Tuple[Dict[str, Any], Optional[str], int]:
    """Create a new study via the API or database directly.
    
    Args:
        name: The name of the study
        analyst_name: The name of the analyst
        
    Returns:
        Tuple[Dict, Optional[str], int]: (response data, error message if any, status code)
    """
    data = {}
    error = None
    status_code = 0
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Study is not None:
        try:
            # Direct database operation instead of HTTP request
            new_study = Study(name=name.strip(), analyst_name=analyst_name.strip())
            db.session.add(new_study)
            db.session.commit()
            
            data = {
                "id": new_study.id,
                "name": new_study.name,
                "analyst_name": new_study.analyst_name,
                "created_at": new_study.created_at.isoformat() if new_study.created_at else None
            }
            status_code = 201
        except Exception as e:
            db.session.rollback()
            error = f'Database error creating study: {e}'
            status_code = 500
            logging.error(f"API Client: Database error creating study: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.studies', _external=True)
        try:
            response = requests.post(api_url, json={
                'name': name.strip(),
                'analyst_name': analyst_name.strip()
            })
            status_code = response.status_code
            data = response.json()
            
            if 'created_at' in data:
                data['created_at'] = _parse_date(data['created_at'])
                
            if status_code != 201:
                error = data.get('error', f'Error creating study (API Status: {status_code}).')
        except requests.RequestException as e:
            error = f'Error connecting to API to create study: {e}'
            logging.error(f"API Client: Failed to connect to API ({api_url}) to create study: {e}")
    
    return data, error, status_code

def get_configurations(study_id: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Get configurations for a study from the API or database directly.
    
    Args:
        study_id: The ID of the study
        
    Returns:
        Tuple[List[Dict], Optional[str]]: (configurations list, error message if any)
    """
    configurations = []
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Configuration is not None:
        try:
            # Direct database operation instead of HTTP request
            study = db.session.get(Study, study_id)
            if not study:
                error = f"Study {study_id} not found."
                return configurations, error
            
            # Get configurations for this study
            config_objects = db.session.query(Configuration).filter_by(study_id=study_id).all()
            
            # Convert to dictionaries
            configurations = []
            for config in config_objects:
                config_dict = {
                    'id': config.id,
                    'study_id': config.study_id,
                    'name': config.name,
                    'phases_n': config.phases_n,
                    'include_bg_dist': config.include_bg_dist,
                    'include_bg_assign': config.include_bg_assign,
                    'include_trip_dist': config.include_trip_dist,
                    'trip_dist_count': config.trip_dist_count,
                    'include_trip_assign': config.include_trip_assign,
                    'created_at': config.created_at.isoformat() if config.created_at else None
                }
                configurations.append(config_dict)
            
            # Process dates in the list
            configurations = _process_dates_in_list(configurations)
            
        except Exception as e:
            error = f'Database error fetching configurations: {e}'
            logging.error(f"API Client: Database error fetching configurations for study {study_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.get_configurations', study_id=study_id, _external=True)
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            configurations = response.json()
            configurations = _process_dates_in_list(configurations)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                error = 'Study not found via API.'
            else:
                error = f'Error fetching configurations from API: {e.response.status_code} - {e.response.text}'
            logging.error(f"API Client: API error fetching configurations ({api_url}): {e}")
        except requests.exceptions.RequestException as e:
            error = f'Error connecting to API to fetch configurations: {e}'
            logging.error(f"API Client: Connection error fetching configurations ({api_url}): {e}")
        except Exception as e:
            error = f'An unexpected error occurred loading the study: {e}'
            logging.error(f"API Client: Unexpected error loading study {study_id}: {e}")
    
    return configurations, error

def configure_study(study_id: int, config_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str], int]:
    """Configure a study via the API or database directly.
    
    Args:
        study_id: The ID of the study
        config_data: Configuration data dictionary
        
    Returns:
        Tuple[Dict, Optional[str], int]: (response data, error message if any, status code)
    """
    data = {}
    error = None
    status_code = 200
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Configuration is not None:
        try:
            # Direct database operation instead of HTTP request
            study = db.session.get(Study, study_id)
            if not study:
                error = f"Study {study_id} not found."
                status_code = 404
                return data, error, status_code
            
            # Validate required fields
            if not config_data or 'phases_n' not in config_data or 'config_name' not in config_data:
                error = "'phases_n' and 'config_name' required"
                status_code = 400
                return data, error, status_code
            
            try:
                n = int(config_data['phases_n'])
                assert n >= 0
            except (ValueError, AssertionError):
                error = "Invalid 'phases_n', must be a non-negative integer."
                status_code = 400
                return data, error, status_code
            
            config_name = config_data['config_name'].strip()
            if not config_name:
                error = "'config_name' cannot be empty"
                status_code = 400
                return data, error, status_code
            
            # Check if configuration name already exists for this study
            existing_config = Configuration.query.filter_by(study_id=study_id, name=config_name).first()
            if existing_config:
                error = f"Configuration name '{config_name}' already exists for this study"
                status_code = 400
                return data, error, status_code
            
            def get_b(p): return config_data.get(p, False) is True
            incl = {k: get_b(k) for k in ['include_bg_dist', 'include_bg_assign', 'include_trip_dist', 'include_trip_assign']}
            
            # Get trip distribution count if trip distribution is included
            trip_dist_count = 1
            if incl['include_trip_dist'] and 'trip_dist_count' in config_data:
                try:
                    trip_dist_count = int(config_data['trip_dist_count'])
                    if trip_dist_count < 1:
                        trip_dist_count = 1
                except (ValueError, TypeError):
                    trip_dist_count = 1
            
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
            
            logging.info(f"API Client: Created configuration '{config_name}' for study {study_id} with {len(scenarios_to_add)} scenarios.")
            s_list = [{"id": s.id, "name": s.name, "status": s.status.name} for s in scenarios_to_add]
            data = {
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
            }
            status_code = 200
            
        except Exception as e:
            db.session.rollback()
            error = f'Database error during configuration: {e}'
            status_code = 500
            logging.error(f"API Client: Database error creating configuration for study {study_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.configure_study', study_id=study_id, _external=True)
        try:
            response = requests.post(api_url, json=config_data)
            status_code = response.status_code
            data = response.json()
            
            if status_code != 200:
                error = data.get('error', f'Error creating configuration (API Status: {status_code}).')
        except requests.RequestException as e:
            error = f'Error connecting to API to create configuration: {e}'
            status_code = 500
            logging.error(f"API Client: Failed to connect to API ({api_url}) to create configuration for study {study_id}: {e}")
    
    return data, error, status_code

def get_scenarios(study_id: int, configuration_id: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Get scenarios for a study from the API or database directly.
    
    Args:
        study_id: The ID of the study
        configuration_id: Optional configuration ID to filter by
        
    Returns:
        Tuple[List[Dict], Optional[str]]: (scenarios list, error message if any)
    """
    scenarios = []
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Scenario is not None:
        try:
            # Direct database operation instead of HTTP request
            study = db.session.get(Study, study_id)
            if not study:
                error = f"Study {study_id} not found."
                return scenarios, error
            
            # Build query for scenarios
            query = db.session.query(Scenario).join(Configuration).filter(Configuration.study_id == study_id)
            
            # Filter by configuration_id if provided
            if configuration_id:
                query = query.filter(Scenario.configuration_id == configuration_id)
            
            # Order by creation time to maintain original order
            scenario_objects = query.order_by(Scenario.created_at.asc()).all()
            
            # Convert to dictionaries
            scenarios = []
            for scenario in scenario_objects:
                scenario_dict = {
                    'id': scenario.id,
                    'configuration_id': scenario.configuration_id,
                    'name': scenario.name,
                    'created_at': scenario.created_at.isoformat() if scenario.created_at else None,
                    'updated_at': scenario.updated_at.isoformat() if scenario.updated_at else None,
                    'status': scenario.status.name if scenario.status else None,
                    'status_message': scenario.status_message
                }
                scenarios.append(scenario_dict)
            
        except Exception as e:
            error = f'Database error fetching scenarios: {e}'
            logging.error(f"API Client: Database error fetching scenarios for study {study_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.get_scenarios', study_id=study_id, _external=True)
        if configuration_id:
            api_url += f"?configuration_id={configuration_id}"
        
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            scenarios = response.json()
        except Exception as e:
            error = f'Error fetching scenarios: {e}'
            logging.error(f"API Client: Error fetching scenarios for study {study_id}: {e}")
    
    return scenarios, error

def get_scenario_status(study_id: int, scenario_id: int) -> Tuple[Dict[str, Any], Optional[str]]:
    """Get status for a specific scenario from the API or database directly.
    
    Args:
        study_id: The ID of the study
        scenario_id: The ID of the scenario
        
    Returns:
        Tuple[Dict, Optional[str]]: (scenario data, error message if any)
    """
    scenario_data = {}
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Scenario is not None:
        try:
            # Direct database operation instead of HTTP request
            # Refresh the session to ensure we get the latest data
            db.session.expire_all()
            scenario = db.session.get(Scenario, scenario_id)
            if not scenario:
                error = 'Scenario not found.'
                return scenario_data, error
            
            # Verify the scenario belongs to the correct study
            config = db.session.get(Configuration, scenario.configuration_id)
            if not config or config.study_id != study_id:
                error = 'Scenario not found.'
                return scenario_data, error
            
            # Build uploaded files info
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
            
            # Convert to dictionary
            scenario_data = {
                'scenario_id': scenario.id,
                'id': scenario.id,
                'configuration_id': scenario.configuration_id,
                'configuration_name': config.name,
                'name': scenario.name,
                'created_at': scenario.created_at.isoformat() if scenario.created_at else None,
                'updated_at': scenario.updated_at.isoformat() if scenario.updated_at else None,
                'status': scenario.status.name if scenario.status else None,
                'status_message': scenario.status_message,
                'uploaded_files': uploaded_files_info,
                # Keep these for any part of the frontend still using them directly
                'has_am_csv': bool(scenario.am_csv_path),
                'has_pm_csv': bool(scenario.pm_csv_path),
                'has_attout': bool(scenario.attout_txt_path),
                'has_merged': bool(scenario.merged_csv_path),
                'has_attin': bool(scenario.attin_txt_path)
            }
            
        except Exception as e:
            error = f'Database error fetching scenario status: {e}'
            logging.error(f"API Client: Database error fetching scenario {scenario_id} status: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.get_scenario_status', study_id=study_id, scenario_id=scenario_id, _external=True)
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            scenario_data = response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                error = 'Scenario not found.'
            else:
                error = f'Error fetching scenario status from API: {e.response.status_code}'
            logging.error(f"API Client: API Error fetching scenario status ({api_url}): {e}")
        except requests.exceptions.RequestException as e:
            error = f'Error connecting to API to fetch scenario status: {e}'
            logging.error(f"API Client: Connection error fetching scenario status ({api_url}): {e}")
        except Exception as e:
            error = f'An unexpected error occurred loading the scenario: {e}'
            logging.error(f"API Client: Unexpected error loading scenario {scenario_id} (study {study_id}): {e}")
    
    return scenario_data, error

def upload_file(study_id: int, scenario_id: int, file_type: str, file) -> Tuple[Dict[str, Any], Optional[str]]:
    """Upload a file for a scenario via the API or database directly.
    
    Args:
        study_id: The ID of the study
        scenario_id: The ID of the scenario
        file_type: The type of file ('am_csv', 'pm_csv', 'attout_txt')
        file: The file object from request.files
        
    Returns:
        Tuple[Dict, Optional[str]]: (response data, error message if any)
    """
    data = {}
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Scenario is not None:
        try:
            from werkzeug.utils import secure_filename
            from traffic_app.utils import validate_file_extension, save_uploaded_file, get_absolute_path
            import os
            
            # Verify scenario exists and belongs to study
            scenario = db.session.get(Scenario, scenario_id)
            if not scenario:
                error = 'Scenario not found.'
                return data, error
            
            config = db.session.get(Configuration, scenario.configuration_id)
            if not config or config.study_id != study_id:
                error = 'Scenario not found in study.'
                return data, error
            
            # Check if scenario is processing
            if scenario.status in [ProcessingStatus.PROCESSING]:
                error = "Cannot upload file while processing is in progress."
                return data, error
            
            # Validate file type
            allowed_types = ['am_csv', 'pm_csv', 'attout_txt']
            if not file_type or file_type not in allowed_types:
                error = f"Invalid 'file_type' (must be one of: {', '.join(allowed_types)})"
                return data, error
            
            # Validate file
            if not file or not file.filename:
                error = "No file selected"
                return data, error
            
            # Validate file extension
            is_valid, error_message = validate_file_extension(file, file_type)
            if not is_valid:
                error = error_message
                return data, error
            
            # Delete existing file if it exists
            existing_file_path_relative = None
            if file_type == 'am_csv' and scenario.am_csv_path:
                existing_file_path_relative = scenario.am_csv_path
                scenario.am_csv_path = None
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
                        logging.info(f"API Client: Deleted existing file '{existing_file_path_absolute}' for scenario {scenario_id}, type {file_type}.")
                except Exception as e:
                    logging.error(f"API Client: Error deleting existing file '{existing_file_path_relative}' for scenario {scenario_id}: {e}")
            
            # Save the file
            original_filename = secure_filename(file.filename)
            relative_save_path, filename = save_uploaded_file(file, study_id, scenario_id, file_type)
            logging.info(f"API Client: Saved file '{filename}' (original: '{original_filename}') for scenario {scenario_id} (type: {file_type}) to {relative_save_path}")
            
            # Update DB path and original name for the specific file type
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
                if scenario.status in [ProcessingStatus.PENDING_CONFIG, ProcessingStatus.PENDING_FILES,
                                       ProcessingStatus.COMPLETE, ProcessingStatus.ERROR]:
                    scenario.status = ProcessingStatus.READY_TO_PROCESS
                    scenario.status_message = "All input files uploaded. Ready to process."
            else:
                if scenario.status != ProcessingStatus.ERROR:
                    scenario.status = ProcessingStatus.PENDING_FILES
                    scenario.status_message = "Waiting for other input file(s)."
            
            db.session.commit()
            db.session.flush()  # Ensure changes are immediately visible
            
            # Log the file path for debugging
            logging.info(f"File saved to: {relative_save_path}, checking if exists: {os.path.exists(get_absolute_path(relative_save_path)) if get_absolute_path(relative_save_path) else 'Path resolution failed'}")
            
            data = {
                "message": f"File '{secure_filename(file.filename)}' uploaded successfully for type '{file_type}'.",
                "saved_filename": filename,
                "scenario_status": scenario.status.name
            }
            
        except Exception as e:
            db.session.rollback()
            error = f'Database error uploading file: {e}'
            logging.error(f"API Client: Database error uploading file: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.upload_scenario_file', study_id=study_id, scenario_id=scenario_id, _external=True)
        
        try:
            files = {'file': (file.filename, file.stream, file.content_type)}
            form_data = {'file_type': file_type}
            response = requests.post(api_url, files=files, data=form_data)
            data = response.json()
            
            if response.status_code != 200:
                error = data.get('error', f'Error uploading file (API Status: {response.status_code}).')
        except requests.RequestException as e:
            error = f'Error connecting to API to upload file: {e}'
            logging.error(f"API Client: Connection error uploading to API ({api_url}): {e}")
    
    return data, error

def process_scenario(study_id: int, scenario_id: int) -> Tuple[Dict[str, Any], Optional[str]]:
    """Process a scenario via the API or database directly.
    
    Args:
        study_id: The ID of the study
        scenario_id: The ID of the scenario
        
    Returns:
        Tuple[Dict, Optional[str]]: (response data, error message if any)
    """
    data = {}
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Scenario is not None:
        try:
            # Import processing function and utilities
            from traffic_app.processing import process_traffic_data
            from traffic_app.utils import get_absolute_path, get_relative_path, get_scenario_folder_path
            import os
            
            # Direct database operation instead of HTTP request
            scenario = db.session.get(Scenario, scenario_id)
            if not scenario:
                error = f"Scenario {scenario_id} not found."
                return data, error
            
            # Verify the scenario belongs to the correct study
            config = db.session.get(Configuration, scenario.configuration_id)
            if not config or config.study_id != study_id:
                error = f"Scenario {scenario_id} not found for study {study_id}."
                return data, error
            
            # Allow reprocessing from ERROR or COMPLETE state too
            allowed_start_states = [ProcessingStatus.READY_TO_PROCESS, ProcessingStatus.ERROR, ProcessingStatus.COMPLETE]
            if scenario.status not in allowed_start_states:
                error = f"Scenario not ready for processing. Current status: {scenario.status.name}. Must be READY, ERROR, or COMPLETE."
                return data, error
            
            # Double-check required files are linked in DB
            required_paths_in_db = [scenario.am_csv_path, scenario.pm_csv_path, scenario.attout_txt_path]
            if not all(required_paths_in_db):
                # If somehow status is READY/COMPLETE/ERROR but paths are missing, update status
                if scenario.status != ProcessingStatus.ERROR:
                    scenario.status = ProcessingStatus.PENDING_FILES
                    scenario.status_message = "Missing required file paths in database record."
                    try: 
                        db.session.commit()
                    except Exception: 
                        db.session.rollback()
                        logging.error("Failed to update status to PENDING_FILES")
                error = "Cannot process: Missing required file paths in database (AM CSV, PM CSV, ATTOUT TXT)."
                return data, error
            
            # Construct absolute paths and verify files exist on disk
            try:
                am_path = get_absolute_path(scenario.am_csv_path)
                pm_path = get_absolute_path(scenario.pm_csv_path)
                attout_path = get_absolute_path(scenario.attout_txt_path)
                output_dir_path = get_scenario_folder_path(study_id, scenario_id, folder_type="outputs")
                
                # Verify actual files exist
                if not os.path.exists(am_path): 
                    raise FileNotFoundError(f"AM file missing on disk: {scenario.am_csv_path}")
                if not os.path.exists(pm_path): 
                    raise FileNotFoundError(f"PM file missing on disk: {scenario.pm_csv_path}")
                if not os.path.exists(attout_path): 
                    raise FileNotFoundError(f"ATTOUT file missing on disk: {scenario.attout_txt_path}")
                    
            except FileNotFoundError as fnf_e:
                logging.error(f"API Client: Required file not found on disk for scenario {scenario_id}: {fnf_e}")
                if scenario.status != ProcessingStatus.ERROR:
                    scenario.status = ProcessingStatus.ERROR
                    scenario.status_message = f"File not found on disk: {os.path.basename(str(fnf_e).split(': ')[-1])}"
                    try: 
                        db.session.commit()
                    except Exception: 
                        db.session.rollback()
                        logging.error("Failed to update status to ERROR for missing file")
                error = f"File missing: {fnf_e}"
                return data, error
            except ValueError as path_e:
                logging.error(f"API Client: Error resolving output path for scenario {scenario_id}: {path_e}")
                if scenario.status != ProcessingStatus.ERROR:
                    scenario.status = ProcessingStatus.ERROR
                    scenario.status_message = f"Path error: {str(path_e)}"
                    try: 
                        db.session.commit()
                    except Exception: 
                        db.session.rollback()
                        logging.error("Failed to update status to ERROR for path issue")
                error = f"Internal path configuration error: {str(path_e)}"
                return data, error
            except Exception as e:
                logging.exception(f"API Client: Unexpected error setting up paths for scenario {scenario_id}: {e}")
                if scenario.status != ProcessingStatus.ERROR:
                    scenario.status = ProcessingStatus.ERROR
                    scenario.status_message = f"Unexpected path setup error: {str(e)}"
                    try: 
                        db.session.commit()
                    except Exception: 
                        db.session.rollback()
                        logging.error("Failed to update status to ERROR for path setup")
                error = f"Unexpected path setup error: {e}"
                return data, error
            
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
                logging.exception(f"API Client: Failed to update status to PROCESSING for scenario {scenario_id}")
                # Re-fetch scenario in case commit failed but object changed
                scenario = db.session.get(Scenario, scenario_id)
                if scenario and scenario.status != ProcessingStatus.ERROR:
                    scenario.status = ProcessingStatus.ERROR
                    scenario.status_message = "Failed to set PROCESSING status in DB."
                    try: 
                        db.session.commit()
                    except Exception: 
                        db.session.rollback()
                error = f"Database error before processing start: {e}"
                return data, error
            
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
                db.session.commit()
                logging.info(f"API Client: Successfully processed scenario {scenario_id} (Study {study_id})")
                
                data = {
                    "message": "Scenario processing completed successfully.",
                    "scenario_id": scenario.id,
                    "status": scenario.status.name,
                    "merged_csv_path": scenario.merged_csv_path,
                    "attin_txt_path": scenario.attin_txt_path
                }
                
            except Exception as e:
                # --- Failure ---
                db.session.rollback()
                # Re-fetch the scenario object within this exception handler's session context
                scenario = db.session.get(Scenario, scenario_id)
                if scenario:
                    scenario.status = ProcessingStatus.ERROR
                    # Be careful about error message length for status_message column
                    error_msg = f"Processing failed: {str(e)}"
                    scenario.status_message = (error_msg[:250] + '...') if len(error_msg) > 253 else error_msg
                    # Ensure output paths are cleared on error
                    scenario.merged_csv_path = None
                    scenario.attin_txt_path = None
                    try:
                        db.session.commit()
                    except Exception as commit_e:
                        db.session.rollback()
                        logging.error(f"API Client: CRITICAL - Failed to commit ERROR status for scenario {scenario_id} after processing failure. DB error: {commit_e}")
                else:
                    logging.error(f"API Client: Scenario {scenario_id} was not found when trying to record processing error.")
                
                logging.exception(f"API Client: Processing failed for scenario {scenario_id} (Study {study_id})")
                error = f"Processing failed: {str(e)}"
                return data, error
                
        except Exception as e:
            db.session.rollback()
            error = f'Database error during processing: {e}'
            logging.error(f"API Client: Database error processing scenario {scenario_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.process_scenario', study_id=study_id, scenario_id=scenario_id, _external=True)
        
        try:
            response = requests.post(api_url)
            data = response.json()
            
            if response.status_code != 200:
                error = data.get('error', f'API Error {response.status_code}')
                logging.error(f"API Client: API error during processing ({api_url}): {response.status_code} - {response.text}")
        except requests.RequestException as e:
            error = f'Error connecting to API to process scenario: {e}'
            logging.error(f"API Client: Connection error processing via API ({api_url}): {e}")
        except Exception as e:
            error = f'An unexpected error occurred triggering processing: {e}'
            logging.error(f"API Client: Unexpected error triggering processing ({api_url}): {e}")
    
    return data, error

def delete_configuration(study_id: int, config_id: int) -> Tuple[Dict[str, Any], Optional[str]]:
    """Delete a configuration via the API or database directly.
    
    Args:
        study_id: The ID of the study
        config_id: The ID of the configuration
        
    Returns:
        Tuple[Dict, Optional[str]]: (response data, error message if any)
    """
    data = {}
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Configuration is not None:
        try:
            # Direct database operation instead of HTTP request
            config = db.session.get(Configuration, config_id)
            if not config or config.study_id != study_id:
                error = f"Configuration {config_id} not found in study {study_id}."
                return data, error
            
            # Import here to avoid circular imports
            from .utils import delete_configuration_folders, delete_scenario_files, delete_scenario_folders
            
            # Track deletion statistics
            total_scenarios = 0
            scenarios_deleted = []
            
            # Get all scenarios for this configuration
            scenarios = Scenario.query.filter_by(configuration_id=config_id).all()
            total_scenarios = len(scenarios)
            
            # Delete each scenario's files and folders
            for scenario in scenarios:
                scenarios_deleted.append(scenario.id)
                delete_scenario_files(scenario)
                delete_scenario_folders(study_id, scenario.id)
                db.session.delete(scenario)
            
            # Delete configuration folders
            delete_configuration_folders(study_id, config_id)
            
            # Delete the configuration itself
            db.session.delete(config)
            db.session.commit()
            
            # Clean up any remaining empty folders
            from .utils import cleanup_all_empty_folders
            cleanup_all_empty_folders()
            
            data = {
                "message": "Configuration deleted successfully",
                "study_id": study_id,
                "config_id": config_id,
                "scenarios_deleted": total_scenarios,
                "scenario_ids_deleted": scenarios_deleted
            }
            
        except Exception as e:
            db.session.rollback()
            error = f'Database error deleting configuration: {e}'
            logging.error(f"API Client: Database error deleting configuration {config_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.delete_configuration', study_id=study_id, config_id=config_id, _external=True)
        try:
            response = requests.delete(api_url)
            data = response.json()
            
            if response.status_code != 200:
                error = data.get('error', f'Error deleting configuration (API Status: {response.status_code}).')
                logging.error(f"API Client: API error deleting configuration ({api_url}): {response.status_code} - {response.text}")
        except requests.RequestException as e:
            error = f'Error connecting to API to delete configuration: {e}'
            logging.error(f"API Client: Connection error deleting configuration via API ({api_url}): {e}")
        except Exception as e:
            error = f'An unexpected error occurred deleting the configuration: {e}'
            logging.error(f"API Client: Unexpected error deleting configuration ({api_url}): {e}")
    
    return data, error

def delete_scenario(study_id: int, scenario_id: int) -> Tuple[Dict[str, Any], Optional[str]]:
    """Delete a scenario via the API or database directly.
    
    Args:
        study_id: The ID of the study
        scenario_id: The ID of the scenario
        
    Returns:
        Tuple[Dict, Optional[str]]: (response data, error message if any)
    """
    data = {}
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Scenario is not None:
        try:
            # Direct database operation instead of HTTP request
            scenario = db.session.get(Scenario, scenario_id)
            if not scenario:
                error = f"Scenario {scenario_id} not found."
                return data, error
            
            # Verify the scenario belongs to the correct study
            config = db.session.get(Configuration, scenario.configuration_id)
            if not config or config.study_id != study_id:
                error = f"Scenario {scenario_id} not found in study {study_id}."
                return data, error
            
            # Import here to avoid circular imports
            from .utils import delete_scenario_files, delete_scenario_folders
            
            # Store configuration ID for response
            configuration_id = scenario.configuration_id
            
            # Delete scenario files and folders
            uploads_deleted, outputs_deleted = delete_scenario_files(scenario)
            delete_scenario_folders(study_id, scenario_id)
            
            # Delete the scenario from database
            db.session.delete(scenario)
            db.session.commit()
            
            # Clean up any remaining empty folders
            from .utils import cleanup_all_empty_folders
            cleanup_all_empty_folders()
            
            data = {
                "message": "Scenario deleted successfully",
                "study_id": study_id,
                "scenario_id": scenario_id,
                "configuration_id": configuration_id,
                "uploads_deleted": uploads_deleted,
                "outputs_deleted": outputs_deleted
            }
            
        except Exception as e:
            db.session.rollback()
            error = f'Database error deleting scenario: {e}'
            logging.error(f"API Client: Database error deleting scenario {scenario_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.delete_scenario', study_id=study_id, scenario_id=scenario_id, _external=True)
        try:
            response = requests.delete(api_url)
            data = response.json()
            
            if response.status_code != 200:
                error = data.get('error', f'Error deleting scenario (API Status: {response.status_code}).')
                logging.error(f"API Client: API error deleting scenario ({api_url}): {response.status_code} - {response.text}")
        except requests.RequestException as e:
            error = f'Error connecting to API to delete scenario: {e}'
            logging.error(f"API Client: Connection error deleting scenario via API ({api_url}): {e}")
        except Exception as e:
            error = f'An unexpected error occurred deleting the scenario: {e}'
            logging.error(f"API Client: Unexpected error deleting scenario ({api_url}): {e}")
    
    return data, error

def delete_study(study_id: int) -> Tuple[Dict[str, Any], Optional[str]]:
    """Delete a study via the API or database directly.
    
    Args:
        study_id: The ID of the study
        
    Returns:
        Tuple[Dict, Optional[str]]: (response data, error message if any)
    """
    data = {}
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Study is not None:
        try:
            # Direct database operation instead of HTTP request
            study = db.session.get(Study, study_id)
            if not study:
                error = f"Study {study_id} not found."
                return data, error
            
            # Import here to avoid circular imports
            from .utils import delete_study_folders
            
            # Track deletion statistics
            total_configs = 0
            total_scenarios = 0
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
                
                # Delete each scenario's files and folders
                for scenario in scenarios:
                    from .utils import delete_scenario_files, delete_scenario_folders
                    delete_scenario_files(scenario)
                    delete_scenario_folders(study_id, scenario.id)
                    db.session.delete(scenario)
                
                # Delete configuration folders
                from .utils import delete_configuration_folders
                delete_configuration_folders(study_id, config_id)
                db.session.delete(config)
            
            # Delete study folders
            delete_study_folders(study_id)
            
            # Delete the study itself
            db.session.delete(study)
            db.session.commit()
            
            # Clean up any remaining empty folders
            from .utils import cleanup_all_empty_folders
            cleanup_all_empty_folders()
            
            data = {
                "message": "Study deleted successfully",
                "study_id": study_id,
                "configurations_deleted": total_configs,
                "scenarios_deleted": total_scenarios,
                "config_ids_deleted": configs_deleted
            }
            
        except Exception as e:
            db.session.rollback()
            error = f'Database error deleting study: {e}'
            logging.error(f"API Client: Database error deleting study {study_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.delete_study', study_id=study_id, _external=True)
        try:
            response = requests.delete(api_url)
            data = response.json()
            
            if response.status_code != 200:
                error = data.get('error', f'Error deleting study (API Status: {response.status_code}).')
                logging.error(f"API Client: API error deleting study ({api_url}): {response.status_code} - {response.text}")
        except requests.RequestException as e:
            error = f'Error connecting to API to delete study: {e}'
            logging.error(f"API Client: Connection error deleting study via API ({api_url}): {e}")
        except Exception as e:
            error = f'An unexpected error occurred deleting the study: {e}'
            logging.error(f"API Client: Unexpected error deleting study ({api_url}): {e}")
    
    return data, error

def update_study(study_id: int, study_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Update a study via the API or database directly.
    
    Args:
        study_id: The ID of the study
        study_data: Dictionary containing the fields to update
        
    Returns:
        Tuple[Dict, Optional[str]]: (response data, error message if any)
    """
    data = {}
    error = None
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Study is not None:
        try:
            # Direct database operation instead of HTTP request
            study = db.session.get(Study, study_id)
            if not study:
                error = f"Study {study_id} not found."
                return data, error
            
            # Update study fields
            if 'name' in study_data:
                study.name = study_data['name'].strip()
            if 'analyst_name' in study_data:
                study.analyst_name = study_data['analyst_name'].strip()
            
            db.session.commit()
            
            data = {
                "id": study.id,
                "name": study.name,
                "analyst_name": study.analyst_name,
                "created_at": study.created_at.isoformat() if study.created_at else None,
                "message": "Study updated successfully"
            }
            
        except Exception as e:
            db.session.rollback()
            error = f'Database error updating study: {e}'
            logging.error(f"API Client: Database error updating study {study_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.update_study', study_id=study_id, _external=True)
        try:
            response = requests.put(api_url, json=study_data)
            data = response.json()
            
            if 'created_at' in data:
                data['created_at'] = _parse_date(data['created_at'])
                
            if response.status_code != 200:
                error = data.get('error', f'Error updating study (API Status: {response.status_code}).')
                logging.error(f"API Client: API error updating study ({api_url}): {response.status_code} - {response.text}")
        except requests.RequestException as e:
            error = f'Error connecting to API to update study: {e}'
            logging.error(f"API Client: Connection error updating study via API ({api_url}): {e}")
        except Exception as e:
            error = f'An unexpected error occurred updating the study: {e}'
            logging.error(f"API Client: Unexpected error updating study ({api_url}): {e}")
    
    return data, error

def delete_scenario_file_api(study_id: int, scenario_id: int, file_type_id: str) -> Tuple[bool, Any]:
    """Calls the API to delete a specific uploaded file for a scenario.
    
    Args:
        study_id: The ID of the study.
        scenario_id: The ID of the scenario.
        file_type_id: The type of file to delete (e.g., 'am_csv', 'pm_csv', 'attout_txt').
        
    Returns:
        Tuple[bool, Any]: (success_flag, data_or_error_message)
          - If successful, data_or_error_message is the JSON response from the API (updated scenario data).
          - If failed, data_or_error_message is an error string.
    """
    error = None
    response_data = None
    success = False
    
    # Check if we should use internal database calls (for production)
    if current_app.config.get('USE_INTERNAL_API', False) and Scenario is not None:
        try:
            # Import required utilities
            from .utils import get_absolute_path
            import os
            
            # Direct database operation instead of HTTP request
            scenario = db.session.get(Scenario, scenario_id)
            if not scenario:
                error = f"Scenario {scenario_id} not found."
                return False, error
            
            # Verify the scenario belongs to the correct study
            config = db.session.get(Configuration, scenario.configuration_id)
            if not config or config.study_id != study_id:
                error = f"Scenario {scenario_id} not found for study {study_id}."
                return False, error
            
            if scenario.status == ProcessingStatus.PROCESSING:
                error = "Cannot delete files while scenario is processing."
                return False, error
            
            valid_file_types = {
                'am_csv': ('am_csv_path', 'am_csv_original_name'),
                'pm_csv': ('pm_csv_path', 'pm_csv_original_name'),
                'attout_txt': ('attout_txt_path', 'attout_txt_original_name')
            }
            
            if file_type_id not in valid_file_types:
                error = f"Invalid file_type_id '{file_type_id}'. Allowed types: {list(valid_file_types.keys())}"
                return False, error
            
            path_attr, name_attr = valid_file_types[file_type_id]
            file_path_relative = getattr(scenario, path_attr, None)
            
            if not file_path_relative:
                logging.warning(f"API Client: No file of type '{file_type_id}' found in DB for scenario {scenario_id} to delete.")
            else:
                try:
                    file_path_absolute = get_absolute_path(file_path_relative)
                    if os.path.exists(file_path_absolute):
                        os.remove(file_path_absolute)
                        logging.info(f"API Client: Successfully deleted physical file: {file_path_absolute}")
                    else:
                        logging.warning(f"API Client: DB path '{file_path_relative}' existed for {file_type_id} of scenario {scenario_id}, but file not on disk at '{file_path_absolute}'.")
                    
                    # Clear DB fields for this file type
                    setattr(scenario, path_attr, None)
                    setattr(scenario, name_attr, None)
                    logging.info(f"API Client: Cleared DB fields for {file_type_id} on scenario {scenario_id}.")
                    
                except Exception as e:
                    db.session.rollback()
                    error = f"Error processing file deletion for {file_type_id}: {str(e)}"
                    logging.error(f"API Client: Error during physical file deletion or DB clear for {file_type_id} of scenario {scenario_id}: {e}")
                    return False, error
            
            # Update scenario status - if it was READY, it might now be PENDING_FILES
            if not all([scenario.am_csv_path, scenario.pm_csv_path, scenario.attout_txt_path]):
                if scenario.status == ProcessingStatus.READY_TO_PROCESS or scenario.status == ProcessingStatus.COMPLETE:
                    scenario.status = ProcessingStatus.PENDING_FILES
                    scenario.status_message = "One or more required files are now missing after deletion."
                    logging.info(f"API Client: Scenario {scenario_id} status updated to PENDING_FILES due to file deletion.")
            
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                error = f"Database error after file deletion: {str(e)}"
                logging.error(f"API Client: Database error committing changes after file deletion for scenario {scenario_id}: {e}")
                return False, error
            
            # Return the updated scenario status
            updated_uploaded_files_info = [
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
            
            response_data = {
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
            }
            
            success = True
            logging.info(f"API Client: Successfully deleted file '{file_type_id}' for scenario {scenario_id}.")
            
        except Exception as e:
            db.session.rollback()
            error = f'Database error during file deletion: {e}'
            logging.error(f"API Client: Database error during file deletion for scenario {scenario_id}: {e}")
    else:
        # Original HTTP-based approach for development
        api_url = url_for('api.delete_scenario_file_typed', 
                            study_id=study_id, 
                            scenario_id=scenario_id, 
                            file_type_id=file_type_id, 
                            _external=True)
        
        logging.info(f"API Client: Attempting to DELETE file '{file_type_id}' for scenario {scenario_id} via {api_url}")
        
        try:
            response = requests.delete(api_url)
            
            if response.status_code == 200: # Expecting 200 OK with updated scenario data
                response_data = response.json()
                logging.info(f"API Client: Successfully deleted file '{file_type_id}'. API response: {response_data}")
                success = True
            elif response.status_code == 204: # No Content is also a valid success for DELETE if no body is returned
                logging.info(f"API Client: Successfully deleted file '{file_type_id}'. API returned 204 No Content.")
                error = f"File deleted, but API returned 204 No Content instead of updated scenario data."
            else:
                try:
                    error_payload = response.json()
                    error = error_payload.get('error', f'API error during file deletion (Status: {response.status_code})')
                except ValueError: # If response is not JSON
                    error = f'API error during file deletion (Status: {response.status_code}, Response: {response.text[:200]})'
                logging.error(f"API Client: Failed to delete file '{file_type_id}'. {error}")
                
        except requests.RequestException as e:
            error = f'API Client: Connection error while deleting file: {e}'
            logging.exception(f"API Client: Connection error to {api_url}: {e}")
    
    if success:
        return True, response_data # response_data should be the updated scenario details
    else:
        return False, error

# --- END OF traffic_app/api_client.py ---
