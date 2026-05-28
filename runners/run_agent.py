import sys
import asyncio
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types
from agents.orchestrator import root_agent

async def run_agent(msg: str):
    runner = InMemoryRunner(agent=root_agent, app_name="cli_copilot")
    session = await runner.session_service.create_session(
        app_name="cli_copilot",
        user_id="cli_user"
    )
    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=msg)]
    )
    
    print("\n--- Agent Execution ---")
    parts = []
    async for event in runner.run_async(
        user_id="cli_user",
        session_id=session.id,
        new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(part.text, end="", flush=True)
                    parts.append(part.text)
    print("\n-----------------------")
    return "".join(parts)

async def main():
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        await run_agent(prompt)
    else:
        print("Welcome to Clinical AI Orchestrator CLI Agent Runner!")
        print("Type 'exit' or 'quit' to end.")
        while True:
            try:
                prompt = input("\nUser> ").strip()
                if not prompt:
                    continue
                if prompt.lower() in ("exit", "quit"):
                    break
                await run_agent(prompt)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
