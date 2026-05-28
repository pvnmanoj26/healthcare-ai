from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from tools import run_bigquery_query
from config.settings import GCP_PROJECT_ID, BIGQUERY_DATASET

model = LiteLlm(model="anthropic/claude-haiku-4-5")
project = GCP_PROJECT_ID or "healthcare-ai-manoj"
dataset = BIGQUERY_DATASET or "healthcare_ai"

analytics_agent = Agent(
    name="analytics_agent",
    model=model,
    description="Runs SQL queries against the BigQuery healthcare dataset to answer analytical questions.",
    instruction=f"""You are a clinical data analyst.
You have access to the BigQuery dataset: {project}.{dataset}
Available tables:
- patients (patient_id, first_name, last_name, birthdate, gender, race, ethnicity, address, city, state, zip)
- conditions (patient_id, code, description, start, stop, status)
- observations (patient_id, code, description, start, value, unit)
- medications (patient_id, code, description, start, stop)
When asked an analytical question:
1. Write a SQL query against the correct table(s).
2. Call run_bigquery_query with the SQL.
3. Summarize the results clearly.""",
    tools=[run_bigquery_query],
)
