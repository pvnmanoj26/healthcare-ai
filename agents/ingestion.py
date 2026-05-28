from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from tools import detect_csv_category, propose_and_preview_mapping, prompt_user_approval, ingest_csv_data

model = LiteLlm(model="anthropic/claude-haiku-4-5")

ingestion_agent = Agent(
    name="ingestion_agent",
    model=model,
    description="Handles clinical file ingestion, category detection, schema mapping, and BigQuery loading.",
    instruction="""You are a clinical data ingestion specialist.
When given a file path:
1. Call detect_csv_category to identify the clinical category.
2. Call propose_and_preview_mapping to generate mappings and get the markdown table preview.
3. Call prompt_user_approval with the preview markdown to get explicit human authorization.
4. Call ingest_csv_data with the file path, category, and approval status to execute the load.
If the user rejects the mapping, do not ingest and report that ingestion was cancelled.""",
    tools=[detect_csv_category, propose_and_preview_mapping, prompt_user_approval, ingest_csv_data],
)
