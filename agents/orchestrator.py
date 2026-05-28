from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from agents.ingestion import ingestion_agent
from agents.analytics import analytics_agent
from agents.care_gap import care_gap_analyst
from agents.search import clinical_search

model = LiteLlm(model="anthropic/claude-haiku-4-5")

root_agent = Agent(
    name="clinical_orchestrator",
    model=model,
    description="Orchestrates clinical AI agents to ingest data, answer questions, and analyze care gaps.",
    instruction="""You are a clinical AI orchestrator.

Route tasks to the right sub-agent:
- Ingesting, loading, or mapping raw clinical data files  → ingestion_agent
- Analytics, SQL queries, counting, aggregations → analytics_agent
- Care gaps, risk analysis, patient lists                 → care_gap_analyst
- Searching notes, clinical questions                     → clinical_search

Synthesise results into a clear clinical report.""",
    sub_agents=[ingestion_agent, analytics_agent, care_gap_analyst, clinical_search],
)
