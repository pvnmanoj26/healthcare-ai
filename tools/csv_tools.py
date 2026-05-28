from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Any
from config.settings import GCP_PROJECT_ID, BIGQUERY_DATASET
from adapters.bigquery import write_demographics_to_bigquery, write_events_to_bigquery
from services.ingestion import (
    profile_csv_file,
    propose_mapping_with_ai,
    save_mapping,
    load_mapping,
    mapping_path,
    mapping_preview_markdown,
    ingest_csv_with_mapping,
)

def detect_csv_category(file_path: str | Path) -> str:
    """
    Detect the clinical category of the CSV file (e.g. patients, medications, conditions).
    """
    from adapters.bigquery import EVENT_TYPE_TO_FIELD
    file_path = Path(file_path)
    stem = file_path.stem.lower()
    
    if stem in EVENT_TYPE_TO_FIELD:
        return stem
        
    if "patient" in stem:
        return "patients"
        
    try:
        profile = profile_csv_file(file_path)
        mapping = propose_mapping_with_ai(profile)
        has_demographics = any(
            str(item.get("target_field") or "").startswith("demographics.") 
            for item in mapping.get("mappings", [])
        )
        return "patients" if has_demographics else "events"
    except Exception:
        return "events"

def propose_and_preview_mapping(file_path: str | Path) -> str:
    """
    Profile the CSV and generate a markdown table preview of the proposed AI mappings.
    """
    file_path = Path(file_path)
    profile = profile_csv_file(file_path)
    mapping = propose_mapping_with_ai(profile)
    save_mapping(mapping, mappings_dir=Path(tempfile.gettempdir()))
    return mapping_preview_markdown(mapping)

def prompt_user_approval(preview_markdown: str) -> bool:
    """
    Present the mapping preview and ask the user for approval.
    """
    print("\n[AI Proposed CSV Schema Mapping Preview]")
    print(preview_markdown)
    print("\n")
    try:
        resp = input("Do you approve this mapping? (yes/no): ").strip().lower()
        return resp in {"yes", "y"}
    except Exception:
        return True

def ingest_csv_data(file_path: str | Path, category: str, approved: bool) -> dict[str, Any]:
    """
    Ingest the CSV file into BigQuery using the approved mapping.
    """
    if not approved:
        return {"success": False, "message": "Ingestion cancelled: Mapping was not approved by user."}
        
    file_path = Path(file_path)
    try:
        mapping_file = mapping_path(file_path.name, mappings_dir=Path(tempfile.gettempdir()))
        if not mapping_file.exists():
            profile = profile_csv_file(file_path)
            mapping = propose_mapping_with_ai(profile)
        else:
            mapping = load_mapping(mapping_file)
            
        mapping["approved"] = True
        records = ingest_csv_with_mapping(file_path, mapping)
        
        project_id = GCP_PROJECT_ID or "healthcare-ai-manoj"
        dataset_id = BIGQUERY_DATASET or "healthcare_ai"
        
        if category == "patients":
            results = write_demographics_to_bigquery(records, project_id, dataset_id)
        else:
            results = write_events_to_bigquery(records, category, project_id, dataset_id)
            
        errors = results.get("errors", [])
        if errors:
            return {"success": False, "error": f"Ingestion completed with errors: {errors}"}
            
        return {
            "success": True,
            "message": f"Successfully ingested {results.get('rows_attempted', 0)} rows into table: '{results.get('table')}'"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
