"""
Central settings — load all environment variables once here.
Every other module imports from this file. No os.getenv() elsewhere.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Anthropic ─────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Google Cloud ──────────────────────────────
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "healthcare-ai-manoj")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "healthcare_ai")
BIGQUERY_PATIENT_TABLE = os.getenv("BIGQUERY_PATIENT_TABLE", "patients")

# ── Upstash Vector ────────────────────────────
UPSTASH_VECTOR_REST_URL = os.getenv("UPSTASH_VECTOR_REST_URL", "")
UPSTASH_VECTOR_REST_TOKEN = os.getenv("UPSTASH_VECTOR_REST_TOKEN", "")

# ── Clinical API (Cloud Run backend) ─────────
CLINICAL_API_BASE_URL = os.getenv(
    "CLINICAL_API_BASE_URL",
    "https://clinical-ai-api-230808425514.us-central1.run.app"
)

# ── Flask ─────────────────────────────────────
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-prod")
PORT = int(os.getenv("PORT", 8080))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
