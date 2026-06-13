from datetime import datetime, date
import json
import re
from typing import Any
from google.cloud import bigquery
from config.settings import GCP_PROJECT_ID, BIGQUERY_DATASET
from models import ClinicalPatientRecord

EVENT_TYPE_TO_FIELD = {
    "allergy": "allergies",
    "allergies": "allergies",
    "careplan": "careplans",
    "careplans": "careplans",
    "condition": "conditions",
    "conditions": "conditions",
    "device": "devices",
    "devices": "devices",
    "encounter": "encounters",
    "encounters": "encounters",
    "imaging_study": "imaging_studies",
    "imaging_studies": "imaging_studies",
    "immunization": "immunizations",
    "immunizations": "immunizations",
    "medication": "medications",
    "medications": "medications",
    "observation": "observations",
    "observations": "observations",
    "procedure": "procedures",
    "procedures": "procedures",
    "supply": "supplies",
    "supplies": "supplies",
}

_client = None

def get_client(project_id: str | None = None) -> bigquery.Client:
    global _client
    if _client is None:
        project = project_id or GCP_PROJECT_ID or "healthcare-ai-manoj"
        _client = bigquery.Client(project=project)
    return _client

def write_demographics_to_bigquery(
    records: list[ClinicalPatientRecord],
    project_id: str | None = None,
    dataset_id: str | None = None,
    table_id: str = "patients",
) -> dict[str, Any]:
    """Writes flat patient demographics to the `patients` table in BigQuery."""
    proj = project_id or GCP_PROJECT_ID or "healthcare-ai-manoj"
    dataset = dataset_id or BIGQUERY_DATASET or "synthea"
    client = get_client(proj)
    table_ref = f"{proj}.{dataset}.{table_id}"

    schema = [
        bigquery.SchemaField("patient_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("first_name", "STRING"),
        bigquery.SchemaField("last_name", "STRING"),
        bigquery.SchemaField("birthdate", "DATE"),
        bigquery.SchemaField("deathdate", "DATE"),
        bigquery.SchemaField("gender", "STRING"),
        bigquery.SchemaField("race", "STRING"),
        bigquery.SchemaField("ethnicity", "STRING"),
        bigquery.SchemaField("address", "STRING"),
        bigquery.SchemaField("city", "STRING"),
        bigquery.SchemaField("state", "STRING"),
        bigquery.SchemaField("zip", "STRING"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    ]
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table, exists_ok=True)

    rows = []
    for record in records:
        payload = record.patient.model_dump(mode="json")
        payload["ingested_at"] = datetime.utcnow().isoformat()
        rows.append(payload)

    if not rows:
        return {"table": table_ref, "rows_attempted": 0, "errors": []}

    try:
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition="WRITE_APPEND",
        )
        job = client.load_table_from_json(rows, table_ref, job_config=job_config)
        job.result()
        errors = job.errors or []
    except Exception as e:
        errors = [{"message": str(e)}]

    return {
        "table": table_ref,
        "rows_attempted": len(rows),
        "errors": errors,
    }

def write_events_to_bigquery(
    records: list[ClinicalPatientRecord],
    event_type: str,
    project_id: str | None = None,
    dataset_id: str | None = None,
    table_id: str | None = None,
) -> dict[str, Any]:
    """Extracts events of a specific category and inserts them into BigQuery."""
    proj = project_id or GCP_PROJECT_ID or "healthcare-ai-manoj"
    dataset = dataset_id or BIGQUERY_DATASET or "synthea"
    client = get_client(proj)
    
    key = str(event_type).strip().lower()
    field_name = EVENT_TYPE_TO_FIELD.get(key, "events")
    
    table_name = table_id or (field_name if field_name != "events" else key)
    table_ref = f"{proj}.{dataset}.{table_name}"

    schema = [
        bigquery.SchemaField("patient_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source_file", "STRING"),
        bigquery.SchemaField("source_id", "STRING"),
        bigquery.SchemaField("encounter_id", "STRING"),
        bigquery.SchemaField("code", "STRING"),
        bigquery.SchemaField("description", "STRING"),
        bigquery.SchemaField("start", "TIMESTAMP"),
        bigquery.SchemaField("stop", "TIMESTAMP"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("value", "STRING"),
        bigquery.SchemaField("unit", "STRING"),
        bigquery.SchemaField("metadata", "STRING"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    ]
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table, exists_ok=True)

    rows = []
    for record in records:
        patient_id = record.patient.patient_id
        if hasattr(record, field_name):
            events = getattr(record, field_name)
            for event in events:
                payload = event.model_dump(mode="json")
                payload["patient_id"] = patient_id
                payload["ingested_at"] = datetime.utcnow().isoformat()
                
                for date_field in ["start", "stop"]:
                    if payload.get(date_field):
                        val = str(payload[date_field]).strip()
                        if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
                            payload[date_field] = f"{val} 00:00:00"

                if "metadata" in payload and isinstance(payload["metadata"], dict):
                    payload["metadata"] = json.dumps(payload["metadata"])
                rows.append(payload)

    if not rows:
        return {
            "table": table_ref,
            "rows_attempted": 0,
            "errors": [],
            "message": f"No events found in records for category: {field_name}"
        }

    try:
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition="WRITE_APPEND",
        )
        job = client.load_table_from_json(rows, table_ref, job_config=job_config)
        job.result()
        errors = job.errors or []
    except Exception as e:
        errors = [{"message": str(e)}]

    return {
        "table": table_ref,
        "rows_attempted": len(rows),
        "errors": errors,
    }

def run_bigquery_query(sql: str, project_id: str | None = None) -> dict[str, Any]:
    """Run a SQL query against the BigQuery healthcare dataset."""
    proj = project_id or GCP_PROJECT_ID or "healthcare-ai-manoj"
    client = get_client(proj)
    try:
        query_job = client.query(sql)
        results = query_job.result()
        rows = [dict(row) for row in results]
        
        for row in rows:
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
        return {"rows": rows, "count": len(rows)}
    except Exception as e:
        return {"error": str(e)}

def write_care_gap_workflow_to_bigquery(
    record: dict[str, Any],
    project_id: str | None = None,
    dataset_id: str | None = None,
    table_id: str = "care_gap_workflows",
) -> dict[str, Any]:
    """Append a completed LangGraph care-gap workflow to BigQuery."""
    proj = project_id or GCP_PROJECT_ID or "healthcare-ai-manoj"
    dataset = dataset_id or BIGQUERY_DATASET or "healthcare_ai"
    table_ref = f"{proj}.{dataset}.{table_id}"
    client = get_client(proj)
    schema = [
        bigquery.SchemaField("workflow_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("patient_note", "STRING"),
        bigquery.SchemaField("summary", "JSON"),
        bigquery.SchemaField("risk_level", "STRING"),
        bigquery.SchemaField("detected_conditions", "JSON"),
        bigquery.SchemaField("approved_gaps", "JSON"),
        bigquery.SchemaField("rejected_gaps", "JSON"),
        bigquery.SchemaField("action_plan", "JSON"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("completed_at", "TIMESTAMP"),
    ]
    client.create_table(bigquery.Table(table_ref, schema=schema), exists_ok=True)

    row = {
        "workflow_id": record.get("workflow_id", ""),
        "patient_note": record.get("patient_note", ""),
        "summary": record.get("summary", {}),
        "risk_level": record.get("risk_level", ""),
        "detected_conditions": record.get("detected_conditions", []),
        "approved_gaps": record.get("approved_gaps", []),
        "rejected_gaps": record.get("rejected_gaps", []),
        "action_plan": record.get("action_plan", {}),
        "status": record.get("status", "complete"),
        "completed_at": datetime.utcnow().isoformat(),
    }
    errors = client.insert_rows_json(table_ref, [row])
    return {"table": table_ref, "rows_attempted": 1, "errors": errors}
