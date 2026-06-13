from types import SimpleNamespace

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import agents.langgraph_workflow as workflow


def _summary(primary_diagnosis: str, comorbidities: list[str] | None = None):
    data = {
        "out_of_scope": False,
        "reason": None,
        "primary_diagnosis": primary_diagnosis,
        "procedure": "",
        "comorbidities": comorbidities or [],
        "medications": [],
        "key_findings": [],
        "risk_flags": [],
        "follow_up_actions": [],
    }
    return SimpleNamespace(model_dump=lambda: data)


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def test_low_risk_bypasses_condition_nodes(monkeypatch):
    protocol_calls = []
    stored = []
    monkeypatch.setattr(workflow, "generate_clinical_summary", lambda note: _summary("Routine visit"))
    monkeypatch.setattr(workflow, "_claude_json", lambda *args, **kwargs: {"risk_level": "LOW"})
    monkeypatch.setattr(workflow, "_protocol_node", lambda condition, state: protocol_calls.append(condition))
    monkeypatch.setattr(
        workflow,
        "write_care_gap_workflow_to_bigquery",
        lambda record: stored.append(record) or {"errors": []},
    )
    graph = workflow.build_workflow(InMemorySaver())

    result = graph.invoke(
        workflow.new_workflow_state("Stable patient", "low-risk"),
        config=_config("low-risk"),
    )

    assert result["status"] == "complete"
    assert protocol_calls == []
    assert stored[0]["risk_level"] == "LOW"


def test_multi_condition_note_fans_out_and_interrupts(monkeypatch):
    protocol_calls = []
    monkeypatch.setattr(
        workflow,
        "generate_clinical_summary",
        lambda note: _summary("Diabetes", ["CHF"]),
    )

    def fake_claude(system_prompt, user_prompt, max_tokens=1800):
        if "risk triage" in system_prompt:
            return {"risk_level": "HIGH"}
        raise AssertionError("Protocol calls should be replaced in this test")

    def fake_protocol(condition, state):
        protocol_calls.append(condition)
        return {
            "protocol_gaps": [
                {
                    "gap": f"{condition} gap",
                    "guideline": f"{condition} guideline",
                    "recommendation": f"Address {condition}",
                    "priority": "HIGH",
                    "condition": condition,
                }
            ]
        }

    monkeypatch.setattr(workflow, "_claude_json", fake_claude)
    monkeypatch.setattr(workflow, "_protocol_node", fake_protocol)
    graph = workflow.build_workflow(InMemorySaver())

    result = graph.invoke(
        workflow.new_workflow_state("Diabetes and CHF", "multi-condition"),
        config=_config("multi-condition"),
    )

    assert result["status"] == "pending_approval"
    assert {"diabetes", "heart_failure"}.issubset(protocol_calls)
    assert len(result["draft_gaps"]) == len(protocol_calls)
    assert "__interrupt__" in result


def test_interrupted_workflow_resumes_with_partial_approval(monkeypatch):
    stored = []
    monkeypatch.setattr(workflow, "generate_clinical_summary", lambda note: _summary("Diabetes"))

    def fake_claude(system_prompt, user_prompt, max_tokens=1800):
        if "risk triage" in system_prompt:
            return {"risk_level": "MEDIUM"}
        if "action plans" in system_prompt:
            return {
                "orders": ["Order HbA1c"],
                "referrals": [],
                "medication_adjustments": [],
                "follow_ups": ["Review in 3 months"],
            }
        raise AssertionError("Unexpected Claude call")

    def fake_protocol(condition, state):
        return {
            "protocol_gaps": [
                {
                    "gap": f"{condition} gap",
                    "guideline": f"{condition} guideline",
                    "recommendation": f"Address {condition}",
                    "priority": "HIGH" if condition == "diabetes" else "LOW",
                    "condition": condition,
                }
            ]
        }

    monkeypatch.setattr(workflow, "_claude_json", fake_claude)
    monkeypatch.setattr(workflow, "_protocol_node", fake_protocol)
    monkeypatch.setattr(
        workflow,
        "write_care_gap_workflow_to_bigquery",
        lambda record: stored.append(record) or {"errors": []},
    )
    graph = workflow.build_workflow(InMemorySaver())
    config = _config("resume")

    interrupted = graph.invoke(
        workflow.new_workflow_state("Diabetes follow-up", "resume"),
        config=config,
    )
    assert interrupted["status"] == "pending_approval"

    completed = graph.invoke(Command(resume={"approved_indexes": [0]}), config=config)

    assert completed["status"] == "complete"
    assert len(completed["approved_gaps"]) == 1
    assert len(completed["rejected_gaps"]) == len(interrupted["draft_gaps"]) - 1
    assert completed["action_plan"]["orders"] == ["Order HbA1c"]
    assert stored[0]["status"] == "complete"
