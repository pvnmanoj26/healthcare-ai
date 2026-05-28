from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from tools import search_clinical_notes, ask_clinical_question

model = LiteLlm(model="anthropic/claude-haiku-4-5")

clinical_search = Agent(
    name="clinical_search",
    model=model,
    description="Searches indexed clinical notes and answers clinical questions.",
    instruction="""You are a clinical knowledge assistant.
Use search_clinical_notes for finding relevant notes.
Use ask_clinical_question for synthesised answers across notes.
Be precise and cite sources.""",
    tools=[search_clinical_notes, ask_clinical_question],
)
