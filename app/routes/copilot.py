import asyncio
from flask import Blueprint, request, render_template
from app.routes.utils import base_context

copilot_bp = Blueprint("copilot", __name__)

@copilot_bp.route("/copilot", methods=["GET", "POST"])
def run_copilot():
    if request.method == "GET":
        return render_template("base.html", **base_context(active_tab="copilot"))
        
    message = request.form.get("message", "")
    if not message.strip():
        return render_template("base.html", **base_context(active_tab="copilot"))

    try:
        from agents.orchestrator import root_agent
        from google.adk.runners import InMemoryRunner
        from google.genai import types as genai_types

        async def run_agent(msg):
            runner = InMemoryRunner(agent=root_agent, app_name="clinical_copilot")
            session = await runner.session_service.create_session(
                app_name="clinical_copilot",
                user_id="web_user"
            )
            content = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=msg)]
            )
            parts = []
            async for event in runner.run_async(
                user_id="web_user",
                session_id=session.id,
                new_message=content
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            parts.append(part.text)
            return "\n".join(parts) if parts else "No response from Copilot."

        response_text = asyncio.run(run_agent(message))

    except Exception as e:
        import traceback
        response_text = f"Error running clinical orchestrator: {e}\n\n{traceback.format_exc()}"

    return render_template(
        "base.html", 
        **base_context(
            copilot_query=message,
            copilot_response=response_text,
            active_tab="copilot"
        )
    )
