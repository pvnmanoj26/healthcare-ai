import uuid
import json
from google.cloud import bigquery
from datetime import datetime, timezone
from config.settings import GCP_PROJECT_ID, BIGQUERY_DATASET
from adapters.bigquery import get_client

# BQ Summaries Table
BQ_TABLE = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.patient_summaries"

def init_db():
    """Ensures BigQuery summary table exists."""
    client = get_client()
    schema = [
        bigquery.SchemaField("patient_id",        "STRING"),
        bigquery.SchemaField("primary_diagnosis",  "STRING"),
        bigquery.SchemaField("procedure",          "STRING"),
        bigquery.SchemaField("comorbidities",      "STRING"),
        bigquery.SchemaField("medications",        "STRING"),
        bigquery.SchemaField("key_findings",       "STRING"),
        bigquery.SchemaField("risk_flags",         "STRING"),
        bigquery.SchemaField("follow_up_actions",  "STRING"),
        bigquery.SchemaField("risk_level",         "STRING"),
        bigquery.SchemaField("source_note",        "STRING"),
        bigquery.SchemaField("created_at",         "TIMESTAMP"),
    ]
    table = bigquery.Table(BQ_TABLE, schema=schema)
    client.create_table(table, exists_ok=True)
    print(f"✅ BigQuery table initialized: {BQ_TABLE}")

def save_patient(summary: dict, source_note: str) -> str:
    """Saves generated LLM summary payload into BigQuery database."""
    client = get_client()
    patient_id = str(uuid.uuid4())[:8].upper()
    flag_count = len(summary.get("risk_flags", []))
    risk_level = "HIGH" if flag_count >= 3 else "MEDIUM" if flag_count >= 1 else "LOW"

    row = {
        "patient_id":        patient_id,
        "primary_diagnosis": summary.get("primary_diagnosis", ""),
        "procedure":         summary.get("procedure", ""),
        "comorbidities":     json.dumps(summary.get("comorbidities", [])),
        "medications":       json.dumps(summary.get("medications", [])),
        "key_findings":      json.dumps(summary.get("key_findings", [])),
        "risk_flags":        json.dumps(summary.get("risk_flags", [])),
        "follow_up_actions": json.dumps(summary.get("follow_up_actions", [])),
        "risk_level":        risk_level,
        "source_note":       source_note,
        "created_at":        datetime.now(timezone.utc).isoformat(),
    }

    errors = client.insert_rows_json(BQ_TABLE, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert error: {errors}")
    return patient_id

def get_all_patients() -> list[dict]:
    """Retrieves all summarized patient profiles sorted by latest."""
    client = get_client()
    query = f"""
        SELECT patient_id, primary_diagnosis, procedure, comorbidities,
               medications, risk_flags, risk_level,
               FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', created_at) as created_at
        FROM `{BQ_TABLE}`
        ORDER BY created_at DESC
    """
    rows = client.query(query).result()
    return [dict(row) for row in rows]

def get_patient_by_id(patient_id: str) -> dict | None:
    """Retrieves a single patient record details by ID."""
    client = get_client()
    query = f"""
        SELECT *
        FROM `{BQ_TABLE}`
        WHERE patient_id = @patient_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("patient_id", "STRING", patient_id)
        ]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return dict(rows[0]) if rows else None

def get_patients_by_risk(risk_level: str) -> list[dict]:
    """Retrieves patient summary profiles filtered by clinical risk levels."""
    client = get_client()
    query = f"""
        SELECT patient_id, primary_diagnosis, procedure, risk_flags,
               risk_level,
               FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', created_at) as created_at
        FROM `{BQ_TABLE}`
        WHERE risk_level = @risk_level
        ORDER BY created_at DESC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("risk_level", "STRING", risk_level)
        ]
    )
    rows = client.query(query, job_config=job_config).result()
    return [dict(row) for row in rows]

def get_patient_stats() -> dict:
    """Returns database summary stats showing breakdown of risk flags."""
    client = get_client()
    query = f"""
        SELECT
            COUNT(*) as total,
            COUNTIF(risk_level = 'HIGH')   as high,
            COUNTIF(risk_level = 'MEDIUM') as medium,
            COUNTIF(risk_level = 'LOW')    as low
        FROM `{BQ_TABLE}`
    """
    try:
        row = list(client.query(query).result())[0]
        return {
            "total":  row.total,
            "high":   row.high,
            "medium": row.medium,
            "low":    row.low
        }
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {"total": 0, "high": 0, "medium": 0, "low": 0}
