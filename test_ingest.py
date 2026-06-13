from pathlib import Path
from adk_agents.ingestion import load_mapping, ingest_csv_with_mapping, write_demographics_to_bigquery, write_events_to_bigquery

# Example path configuration
DATA_DIR = Path("/home/vscode/.devcontainer/generative-ai-for-beginners/data/synthea_sample_data_csv_latest")
PROJECT_ID = "your-gcp-project-id"
DATASET_ID = "clinical_dataset"

def run_test():
    # 1. Patients demographics test
    try:
        patients_mapping = load_mapping("adk_agents/mappings/patients.mapping.json")
        patients = ingest_csv_with_mapping(DATA_DIR / "patients.csv", patients_mapping)
        print(f"Ingested {len(patients)} patients in memory.")
        # To test writing to BigQuery, set your GCP configurations above and uncomment:
        # print(write_demographics_to_bigquery(patients, PROJECT_ID, DATASET_ID))
    except Exception as e:
        print("Error ingesting patients:", e)

    # 2. Conditions test
    try:
        conditions_mapping = load_mapping("adk_agents/mappings/conditions.mapping.json")
        conditions = ingest_csv_with_mapping(DATA_DIR / "conditions.csv", conditions_mapping)
        print(f"Ingested {len(conditions)} patient records with conditions in memory.")
        # To test writing to BigQuery, set your GCP configurations above and uncomment:
        # print(write_events_to_bigquery(conditions, "conditions", PROJECT_ID, DATASET_ID))
    except Exception as e:
        print("Error ingesting conditions:", e)

if __name__ == "__main__":
    run_test()
