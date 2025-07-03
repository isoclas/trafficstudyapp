import os
import logging
import pandas as pd
from werkzeug.utils import secure_filename

# Define constants specific to processing
MOVEMENT_COLS = ['EBU','EBL','EBT','EBR','WBU','WBL','WBT','WBR','NBU','NBL','NBT','NBR','SBU','SBL','SBT','SBR']
MIN_INPUT_COLS = ['RECORDNAME', 'INTID'] + MOVEMENT_COLS
ATTOUT_MIN_COLS = ['HANDLE', 'BLOCKNAME', 'NODE_ID']

# ** UPDATED: Added attout_txt_path argument **
def process_traffic_data(am_csv_path, pm_csv_path, attout_txt_path, output_dir, scenario_name):
    """
    Processes AM/PM CSV and ATTOUT TXT files to generate Merged CSV and ATTIN TXT files.
    Uses E/S -> (PM)AM, W/N -> AM(PM) formatting.
    Generates Tab-delimited ATTIN with Header and Blockname, matching ATTOUT structure.
    
    Note: output_dir should already be a path specific to the scenario using the proper folder structure.
    """
    logging.info(f"Starting processing for scenario: {scenario_name}")
    logging.info(f"AM Path: {am_csv_path}")
    logging.info(f"PM Path: {pm_csv_path}")
    logging.info(f"ATTOUT Path: {attout_txt_path}") # Added log
    logging.info(f"Output Dir: {output_dir}")

    merged_csv_output_path = None # Initialize output paths
    attin_txt_output_path = None

    try:
        # --- Step 1 & 2: Read AM/PM CSV Data ---
        logging.info("Reading AM CSV...")
        df_am = pd.read_csv(am_csv_path, dtype={'INTID': str}, skiprows=1)
        if not all(col in df_am.columns for col in MIN_INPUT_COLS): raise ValueError("AM CSV is missing required columns.")
        df_am = df_am[df_am['RECORDNAME'] == 'Volume'].copy()[['INTID'] + MOVEMENT_COLS].set_index('INTID')
        for col in MOVEMENT_COLS: df_am[col] = pd.to_numeric(df_am[col], errors='coerce')
        df_am = df_am.add_suffix('_am')
        logging.info(f"Read {len(df_am)} AM volume records.")

        logging.info("Reading PM CSV...")
        df_pm = pd.read_csv(pm_csv_path, dtype={'INTID': str}, skiprows=1)
        if not all(col in df_pm.columns for col in MIN_INPUT_COLS): raise ValueError("PM CSV is missing required columns.")
        df_pm = df_pm[df_pm['RECORDNAME'] == 'Volume'].copy()[['INTID'] + MOVEMENT_COLS].set_index('INTID')
        for col in MOVEMENT_COLS: df_pm[col] = pd.to_numeric(df_pm[col], errors='coerce')
        df_pm = df_pm.add_suffix('_pm')
        logging.info(f"Read {len(df_pm)} PM volume records.")

        # --- Step 3: Merge AM and PM Data ---
        logging.info("Merging AM and PM data...")
        df_merged = pd.merge(df_am, df_pm, left_index=True, right_index=True, how='outer')
        logging.info(f"Merged data has {len(df_merged)} nodes.")
        logging.debug(f"Merged DataFrame index type: {df_merged.index.dtype}")
        logging.debug(f"Sample Merged index (first 10): {df_merged.index.tolist()[:10]}")

        # --- Step 4: Generate Combined Volume Strings ---
        merged_cols_map = {}
        logging.info("Generating combined AM/PM strings with E/S=(PM)AM, W/N=AM(PM) format...")
        for move in MOVEMENT_COLS:
            col_am, col_pm, col_merged = f'{move}_am', f'{move}_pm', f'{move}_merged'
            merged_cols_map[move] = col_merged
            def calculate_merged_string(row):
                am_val, pm_val = row.get(col_am), row.get(col_pm)
                am_str = str(int(am_val)) if pd.notna(am_val) else '-'
                pm_str = str(int(pm_val)) if pd.notna(pm_val) else '-'
                if move.startswith(('E', 'S')): return f"({pm_str}){am_str}"
                else: return f"{am_str}({pm_str})"
            df_merged[col_merged] = df_merged.apply(calculate_merged_string, axis=1)

        # --- Step 5: (Optional) Prepare and Save Merged CSV Output ---
        merged_csv_filename = f"{secure_filename(scenario_name)}_Merged.csv"
        merged_csv_output_path = os.path.join(output_dir, merged_csv_filename)
        df_merged_output = df_merged[[merged_cols_map[m] for m in MOVEMENT_COLS]].copy()
        df_merged_output.index.name = 'Node ID'
        df_merged_output.rename(columns=lambda x: x.replace('_merged', ''), inplace=True)
        df_merged_output.to_csv(merged_csv_output_path, index=True)
        logging.info(f"Merged CSV saved to: {merged_csv_output_path}")

        # --- Step 6: Read ATTOUT Data ---
        logging.info("Reading ATTOUT TXT...")
        try:
            with open(attout_txt_path, 'r', encoding='utf-8') as f:
                attout_lines = f.readlines()
        except FileNotFoundError: raise ValueError(f"ATTOUT file not found at {attout_txt_path}")
        except Exception as e: raise ValueError(f"Error reading ATTOUT file: {e}")
        if not attout_lines: raise ValueError("ATTOUT file is empty.")

        attout_header_raw = attout_lines[0].strip()
        if '\t' not in attout_header_raw: raise ValueError("ATTOUT file header does not appear to be tab-delimited.")
        attout_header_cols = [h.strip() for h in attout_header_raw.split('\t')]
        logging.info(f"ATTOUT Header Read: {attout_header_cols}")
        if not all(col in attout_header_cols for col in ATTOUT_MIN_COLS):
            missing = [c for c in ATTOUT_MIN_COLS if c not in attout_header_cols]
            raise ValueError(f"ATTOUT file header missing required columns: {', '.join(missing)}")

        attout_movement_order = [col for col in attout_header_cols if col in MOVEMENT_COLS]
        if len(attout_movement_order) != 16:
             logging.warning(f"ATTOUT header contains {len(attout_movement_order)} recognized movement tags (expected 16). ATTIN generation might be missing columns. Found: {attout_movement_order}")

        attout_data_parsed = []
        for i, line in enumerate(attout_lines[1:]):
            line_content = line.strip()
            if not line_content: continue
            logging.debug(f"Raw ATTOUT line {i+2} content before split: {repr(line_content)}")
            parts = [p.strip() for p in line_content.split('\t')]
            logging.debug(f"ATTOUT line {i+2} parts after split('\\t'): {parts} (Count: {len(parts)})")

            if len(parts) < 3:
                logging.warning(f"Skipping ATTOUT line {i+2}: Too few columns ({len(parts)} < 3).")
                continue
            if len(parts) < len(attout_header_cols):
                parts.extend([''] * (len(attout_header_cols) - len(parts)))
                logging.info(f"Padded ATTOUT line {i+2} from {len(parts)} to {len(attout_header_cols)} columns.")
            attout_data_parsed.append(dict(zip(attout_header_cols, parts)))
        logging.info(f"Read {len(attout_data_parsed)} data rows from ATTOUT.")

        # --- Step 7: Generate ATTIN Data ---
        logging.info("Generating ATTIN data lines...")
        attin_data_lines = []
        processed_handles = set()
        nodes_not_found_in_merge = []
        handles_missing_required_info = []
        merged_data_dict = df_merged[[merged_cols_map[m] for m in MOVEMENT_COLS]].to_dict('index')
        logging.debug(f"Merged data dictionary keys (first 10): {list(merged_data_dict.keys())[:10]}")

        for att_row_dict in attout_data_parsed:
            handle = att_row_dict.get('HANDLE')
            blockname = att_row_dict.get('BLOCKNAME')
            node_id_str = att_row_dict.get('NODE_ID')
            logging.debug(f"Processing ATTOUT row for HANDLE: {handle}, Raw NODE_ID: '{node_id_str}'")

            if not handle or not blockname or not node_id_str:
                logging.warning(f"Skipping ATTOUT row due to missing HANDLE, BLOCKNAME, or NODE_ID: {att_row_dict}")
                handles_missing_required_info.append(str(handle or 'UNKNOWN'))
                continue
            node_id_str = node_id_str.strip()
            if not node_id_str:
                 logging.warning(f"Skipping ATTOUT row for HANDLE: {handle} due to empty NODE_ID after stripping.")
                 handles_missing_required_info.append(str(handle or 'UNKNOWN'))
                 continue

            logging.debug(f"Attempting lookup in merged data with NODE_ID key: '{node_id_str}' (Type: {type(node_id_str)})")
            if handle in processed_handles:
                logging.warning(f"Duplicate HANDLE '{handle}' in ATTOUT. Skipping.")
                continue
            processed_handles.add(handle)

            node_volume_data = merged_data_dict.get(node_id_str)
            if node_volume_data:
                logging.debug(f"  -> Found merged data for NODE_ID '{node_id_str}'. Building ATTIN line.")
                output_row_parts = [handle, blockname, node_id_str]
                for movement_key in attout_movement_order:
                    merged_col_name = merged_cols_map.get(movement_key)
                    if merged_col_name:
                        value_str = node_volume_data.get(merged_col_name)
                        if value_str == "-(-)" or pd.isna(value_str): output_row_parts.append("")
                        else: output_row_parts.append(str(value_str))
                    else:
                        logging.warning(f"Movement key '{movement_key}' from ATTOUT order not found for HANDLE {handle}. Appending empty.")
                        output_row_parts.append("")
                logging.debug(f"      -> ATTIN row parts before join: {output_row_parts}")
                attin_data_lines.append("\t".join(output_row_parts))
            else:
                logging.warning(f"  -> FAILED lookup for NODE_ID '{node_id_str}'. No merged data found. Skipping ATTIN line.")
                nodes_not_found_in_merge.append(node_id_str)
                handles_missing_required_info.append(handle)

        if nodes_not_found_in_merge: logging.warning(f"Summary: {len(set(nodes_not_found_in_merge))} unique Node IDs from ATTOUT not found in merged data: {list(set(nodes_not_found_in_merge))}")
        if handles_missing_required_info: logging.warning(f"Summary: ATTIN lines not generated for {len(set(handles_missing_required_info))} HANDLEs due to issues.")

        # --- Step 8: Assemble and Save ATTIN File ---
        attin_txt_filename = f"{secure_filename(scenario_name)}_ATTIN.txt"
        attin_txt_output_path = os.path.join(output_dir, attin_txt_filename)
        logging.info(f"Writing ATTIN file (with header): {attin_txt_output_path}")
        with open(attin_txt_output_path, 'w', encoding='utf-8') as f:
            f.write(attout_header_raw + "\n")
            f.write("\n".join(attin_data_lines))

        logging.info(f"Processing complete for scenario: {scenario_name}")
        return merged_csv_output_path, attin_txt_output_path

    except FileNotFoundError as e: logging.error(f"File not found error: {e}"); raise Exception(f"Input file not found: {e.filename}") from e
    except pd.errors.EmptyDataError as e: logging.error(f"Empty input file error: {e}"); raise Exception(f"Input CSV or ATTOUT file is empty/invalid.") from e
    except ValueError as e: logging.error(f"Data validation/format error: {e}"); raise Exception(f"Data Error: {e}") from e
    except KeyError as e: logging.error(f"Missing key error: {e}"); raise Exception(f"Missing data column: {e}") from e
    except Exception as e: logging.exception(f"Unexpected error processing scenario {scenario_name}"); raise Exception(f"Unexpected error: {e}") from e