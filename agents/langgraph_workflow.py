import json
import operator
import uuid
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt

from adapters.anthropic import get_claude_response
from adapters.bigquery import write_care_gap_workflow_to_bigquery
from models import CareGapResult
from services.clinical_summary import (
    GUIDELINES,
    clean_json,
    detect_conditions,
    generate_clinical_summary,
    retrieve_relevant_guidelines,
)


class GraphState(TypedDict, total=False):
    workflow_id: str
    patient_note: str
    summary: dict[str, Any]
    risk_level: str
    detected_conditions: list[str]
    protocol_gaps: Annotated[list[dict[str, Any]], operator.add]
    draft_gaps: list[dict[str, Any]]
    approved_gaps: list[dict[str, Any]]
    rejected_gaps: list[dict[str, Any]]
    action_plan: dict[str, Any]
    status: str
    storage_result: dict[str, Any]


PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
SUPPORTED_CONDITIONS = {"diabetes", "heart_failure", "ckd", "general"}


def _claude_json(system_prompt: str, user_prompt: str, max_tokens: int = 1800) -> dict[str, Any]:
    raw = get_claude_response(
        system_prompt,
        user_prompt,
        max_tokens=max_tokens,
        temperature=0.0,
    )
    cleaned = clean_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from Claude. Raw response: {raw[:200]}... Error: {str(e)}") from e


def summarize_node(state: GraphState) -> dict[str, Any]:
    summary = generate_clinical_summary(state["patient_note"]).model_dump()
    return {"summary": summary, "status": "triage"}


def risk_triage_node(state: GraphState) -> dict[str, Any]:
    result = _claude_json(
        "You are a clinical risk triage assistant. Return JSON only as "
        '{"risk_level":"LOW|MEDIUM|HIGH"}. Base severity only on the supplied facts.',
        json.dumps(state["summary"]),
        max_tokens=200,
    )
    risk_level = str(result.get("risk_level", "MEDIUM")).upper()
    if risk_level not in PRIORITY_ORDER:
        risk_level = "MEDIUM"
    return {"risk_level": risk_level, "status": "triage_complete"}


def route_after_triage(state: GraphState) -> str:
    return "store" if state.get("risk_level") == "LOW" else "gap_detection"


def gap_detection_node(state: GraphState) -> dict[str, Any]:
    detected = detect_conditions(state["summary"])
    routed = sorted(detected.intersection(SUPPORTED_CONDITIONS - {"general"}))
    if not routed:
        routed = ["general"]
    return {"detected_conditions": routed, "status": "evaluating_gaps"}


def route_to_conditions(state: GraphState) -> list[Send]:
    return [
        Send(f"{condition}_protocol", state)
        for condition in state.get("detected_conditions", ["general"])
    ]


def _condition_guidelines(condition: str, state: GraphState) -> list[str]:
    retrieved = retrieve_relevant_guidelines(
        state["patient_note"],
        state.get("summary"),
        k=12,
    )
    scoped = [
        guideline["text"]
        for guideline in GUIDELINES
        if guideline["condition"] == condition and guideline["text"] in retrieved
    ]
    if not scoped:
        scoped = [
            guideline["text"]
            for guideline in GUIDELINES
            if guideline["condition"] == condition
        ]
    return scoped


def _protocol_node(condition: str, state: GraphState) -> dict[str, Any]:
    guidelines = _condition_guidelines(condition, state)
    result = _claude_json(
        "You are a clinical care-gap evaluator. Evaluate only the supplied "
        f"{condition} guidelines. Return JSON matching "
        '{"gaps":[{"gap":"string","guideline":"string",'
        '"recommendation":"string","priority":"HIGH|MEDIUM|LOW"}],'
        '"summary":"string"}. Only report care explicitly missing or incomplete.\n\n'
        + "\n".join(f"- {item}" for item in guidelines),
        json.dumps({"note": state["patient_note"], "summary": state["summary"]}),
    )
    gaps = CareGapResult(**result).model_dump()["gaps"]
    for gap in gaps:
        gap["condition"] = condition
    return {"protocol_gaps": gaps}


def diabetes_protocol_node(state: GraphState) -> dict[str, Any]:
    return _protocol_node("diabetes", state)


def heart_failure_protocol_node(state: GraphState) -> dict[str, Any]:
    return _protocol_node("heart_failure", state)


def ckd_protocol_node(state: GraphState) -> dict[str, Any]:
    return _protocol_node("ckd", state)


def general_protocol_node(state: GraphState) -> dict[str, Any]:
    return _protocol_node("general", state)


def gap_prioritizer_node(state: GraphState) -> dict[str, Any]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for gap in state.get("protocol_gaps", []):
        key = (gap.get("gap", "").strip().lower(), gap.get("guideline", "").strip().lower())
        current = unique.get(key)
        if current is None or PRIORITY_ORDER.get(gap.get("priority", "MEDIUM"), 1) < PRIORITY_ORDER.get(current.get("priority", "MEDIUM"), 1):
            unique[key] = gap
    prioritized = sorted(
        unique.values(),
        key=lambda gap: PRIORITY_ORDER.get(gap.get("priority", "MEDIUM"), 1),
    )
    return {"draft_gaps": prioritized, "status": "pending_approval"}


def human_approval_node(state: GraphState) -> dict[str, Any]:
    decision = interrupt(
        {
            "workflow_id": state["workflow_id"],
            "summary": state["summary"],
            "risk_level": state["risk_level"],
            "gaps": state.get("draft_gaps", []),
        }
    )
    approved_indexes = {int(index) for index in decision.get("approved_indexes", [])}
    gaps = state.get("draft_gaps", [])
    approved = [gap for index, gap in enumerate(gaps) if index in approved_indexes]
    rejected = [gap for index, gap in enumerate(gaps) if index not in approved_indexes]
    return {
        "approved_gaps": approved,
        "rejected_gaps": rejected,
        "status": "approved" if approved else "rejected",
    }


def route_after_approval(state: GraphState) -> str:
    return "generate_action_plan" if state.get("approved_gaps") else "store"


def action_plan_node(state: GraphState) -> dict[str, Any]:
    action_plan = _claude_json(
        "You create clinician-reviewable care-gap action plans. Return JSON only with "
        'keys "orders", "referrals", "medication_adjustments", and "follow_ups", '
        "each containing a list of strings. Do not add actions unrelated to approved gaps.",
        json.dumps({"summary": state["summary"], "approved_gaps": state["approved_gaps"]}),
    )
    return {"action_plan": action_plan, "status": "action_plan_generated"}


def bigquery_store_node(state: GraphState) -> dict[str, Any]:
    final_status = "complete" if state.get("status") != "rejected" else "rejected"
    record = dict(state)
    record["status"] = final_status
    result = write_care_gap_workflow_to_bigquery(record)
    return {"storage_result": result, "status": final_status}


def build_workflow(checkpointer: InMemorySaver | None = None):
    builder = StateGraph(GraphState)
    builder.add_node("summarize", summarize_node)
    builder.add_node("risk_triage", risk_triage_node)
    builder.add_node("gap_detection", gap_detection_node)
    builder.add_node("diabetes_protocol", diabetes_protocol_node)
    builder.add_node("heart_failure_protocol", heart_failure_protocol_node)
    builder.add_node("ckd_protocol", ckd_protocol_node)
    builder.add_node("general_protocol", general_protocol_node)
    builder.add_node("prioritize", gap_prioritizer_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("generate_action_plan", action_plan_node)
    builder.add_node("store", bigquery_store_node)

    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", "risk_triage")
    builder.add_conditional_edges(
        "risk_triage",
        route_after_triage,
        {"store": "store", "gap_detection": "gap_detection"},
    )
    builder.add_conditional_edges("gap_detection", route_to_conditions)
    for node in (
        "diabetes_protocol",
        "heart_failure_protocol",
        "ckd_protocol",
        "general_protocol",
    ):
        builder.add_edge(node, "prioritize")
    builder.add_edge("prioritize", "human_approval")
    builder.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {"generate_action_plan": "generate_action_plan", "store": "store"},
    )
    builder.add_edge("generate_action_plan", "store")
    builder.add_edge("store", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


checkpointer = InMemorySaver()
care_gap_graph = build_workflow(checkpointer)


def new_workflow_state(patient_note: str, workflow_id: str | None = None) -> GraphState:
    return {
        "workflow_id": workflow_id or str(uuid.uuid4()),
        "patient_note": patient_note,
        "protocol_gaps": [],
        "draft_gaps": [],
        "approved_gaps": [],
        "rejected_gaps": [],
        "action_plan": {},
        "status": "started",
    }


def workflow_config(workflow_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": workflow_id}}


def start_workflow(patient_note: str, workflow_id: str | None = None) -> dict[str, Any]:
    state = new_workflow_state(patient_note, workflow_id)
    return care_gap_graph.invoke(state, config=workflow_config(state["workflow_id"]))


def resume_workflow(workflow_id: str, approved_indexes: list[int]) -> dict[str, Any]:
    return care_gap_graph.invoke(
        Command(resume={"approved_indexes": approved_indexes}),
        config=workflow_config(workflow_id),
    )


def get_workflow_state(workflow_id: str) -> dict[str, Any]:
    snapshot = care_gap_graph.get_state(workflow_config(workflow_id))
    return dict(snapshot.values) if snapshot.values else {}
