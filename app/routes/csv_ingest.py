import os
import tempfile
import uuid
from pathlib import Path
from flask import Blueprint, request, render_template, session
from app.routes.utils import base_context
from config.settings import GCP_PROJECT_ID, BIGQUERY_DATASET
from adapters.bigquery import write_demographics_to_bigquery, write_events_to_bigquery, EVENT_TYPE_TO_FIELD
from services.ingestion import (
    profile_csv_file,
    propose_mapping_with_ai,
    ingest_csv_with_mapping,
)

csv_ingest_bp = Blueprint("csv_ingest", __name__)

@csv_ingest_bp.route("/csv-ingest")
def csv_ingest_page():
    return render_template("base.html", **base_context(active_tab="csv_ingest"))

@csv_ingest_bp.route("/csv-ingest/upload", methods=["POST"])
def csv_ingest_upload():
    if "csv_file" not in request.files:
        return render_template("base.html", **base_context(
            active_tab="csv_ingest",
            csv_ingest_error="No file part in request"
        ))
    
    file = request.files["csv_file"]
    if file.filename == "":
        return render_template("base.html", **base_context(
            active_tab="csv_ingest",
            csv_ingest_error="No selected file"
        ))

    if not file.filename.endswith(".csv"):
        return render_template("base.html", **base_context(
            active_tab="csv_ingest",
            csv_ingest_error="File must be a CSV (.csv)"
        ))

    temp_subdir = os.path.join(tempfile.gettempdir(), f"upload_{uuid.uuid4().hex}")
    os.makedirs(temp_subdir, exist_ok=True)
    temp_path = os.path.join(temp_subdir, file.filename)
    file.save(temp_path)

    try:
        profile = profile_csv_file(temp_path)
        mapping = propose_mapping_with_ai(profile)
        
        has_demographics = any(
            str(item.get("target_field") or "").startswith("demographics.") 
            for item in mapping.get("mappings", [])
        )
        category = "patients" if has_demographics else "events"
        
        if category == "events":
            stem = Path(file.filename).stem.lower()
            if stem in EVENT_TYPE_TO_FIELD:
                category = stem

        session["temp_csv_path"] = temp_path
        session["temp_csv_name"] = file.filename
        session["proposed_mapping"] = mapping
        session["proposed_category"] = category

        return render_template("mapping_preview.html", 
                               filename=file.filename,
                               category=category,
                               mapping=mapping)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            try:
                os.rmdir(os.path.dirname(temp_path))
            except Exception:
                pass
        print(f"Error profiling CSV: {e}")
        return render_template("base.html", **base_context(
            active_tab="csv_ingest",
            csv_ingest_error=f"Error profiling/mapping CSV: {str(e)}"
        ))

@csv_ingest_bp.route("/csv-ingest/confirm", methods=["POST"])
def csv_ingest_confirm():
    temp_path = session.get("temp_csv_path")
    filename = session.get("temp_csv_name")
    mapping = session.get("proposed_mapping")
    category = session.get("proposed_category")
    action = request.form.get("action", "reject")

    if not temp_path or not os.path.exists(temp_path):
        return render_template("base.html", **base_context(
            active_tab="csv_ingest",
            csv_ingest_error="Session expired or file not found. Please upload again."
        ))

    if action == "reject":
        if os.path.exists(temp_path):
            os.remove(temp_path)
            try:
                os.rmdir(os.path.dirname(temp_path))
            except Exception:
                pass
        session.pop("temp_csv_path", None)
        session.pop("temp_csv_name", None)
        session.pop("proposed_mapping", None)
        session.pop("proposed_category", None)
        return render_template("base.html", **base_context(
            active_tab="csv_ingest",
            csv_ingest_message="Ingestion cancelled by user. Proposed mapping discarded."
        ))

    try:
        mapping["approved"] = True
        records = ingest_csv_with_mapping(temp_path, mapping)
        
        project_id = GCP_PROJECT_ID or "healthcare-ai-manoj"
        dataset_id = BIGQUERY_DATASET or "healthcare_ai"
        
        if category == "patients":
            results = write_demographics_to_bigquery(records, project_id, dataset_id)
        else:
            results = write_events_to_bigquery(records, category, project_id, dataset_id)

        if os.path.exists(temp_path):
            os.remove(temp_path)
            try:
                os.rmdir(os.path.dirname(temp_path))
            except Exception:
                pass
        session.pop("temp_csv_path", None)
        session.pop("temp_csv_name", None)
        session.pop("proposed_mapping", None)
        session.pop("proposed_category", None)

        rows_loaded = results.get("rows_attempted", 0)
        errors = results.get("errors", [])
        
        if errors:
            return render_template("base.html", **base_context(
                active_tab="csv_ingest",
                csv_ingest_error=f"Ingested {rows_loaded} rows, but database errors occurred: {errors}"
            ))
        else:
            return render_template("base.html", **base_context(
                active_tab="csv_ingest",
                csv_ingest_message=f"🎉 Successfully ingested {rows_loaded} rows from '{filename}' into table '{results.get('table')}'!"
            ))

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            try:
                os.rmdir(os.path.dirname(temp_path))
            except Exception:
                pass
        print(f"Error executing ingestion: {e}")
        return render_template("base.html", **base_context(
            active_tab="csv_ingest",
            csv_ingest_error=f"Ingestion execution failed: {str(e)}"
        ))
