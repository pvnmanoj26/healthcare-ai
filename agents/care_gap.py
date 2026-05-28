from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from tools import list_patients, get_population_gaps

model = LiteLlm(model="anthropic/claude-haiku-4-5")

care_gap_analyst = Agent(
    name="care_gap_analyst",
    model=model,
    description="Analyses patient populations to identify and prioritise care gaps.",
    instruction="""You are a clinical care gap analyst.
Use get_population_gaps to analyse multiple patients efficiently.
Always sort gaps by priority — HIGH first.
Be concise and cite patient IDs.""",
    tools=[list_patients, get_population_gaps],
)
