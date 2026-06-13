from typing import Any

from flask import Blueprint, jsonify, render_template, request

from agents.langgraph_workflow import (
    get_workflow_state,
    resume_workflow,
    start_workflow,
)
from app.routes.utils import base_context


langgraph_bp = Blueprint("langgraph", __name__, url_prefix="/langgraph")
_workflow_index: dict[str, dict[str, Any]] = {}


def _pending_workflows() -> list[dict[str, Any]]:
    pending = []
    for workflow_id in list(_workflow_index):
        state = get_workflow_state(workflow_id)
        if state:
            _workflow_index[workflow_id] = state
        if state.get("status") == "pending_approval":
            pending.append(state)
    return pending


def _wants_json() -> bool:
    return request.is_json or request.args.get("format") == "json"


@langgraph_bp.post("/start")
def start():
    import traceback
    from flask import current_app

    payload = request.get_json(silent=True) or request.form
    note = str(payload.get("patient_note") or payload.get("clinical_note") or "").strip()
    if not note:
        message = "A patient note is required."
        if _wants_json():
            return jsonify({"error": message}), 400
        return render_template(
            "base.html",
            **base_context(active_tab="langgraph", langgraph_error=message),
        ), 400

    try:
        current_app.logger.info("Starting workflow...")
        result = start_workflow(note)
        current_app.logger.info(f"Workflow result: {result}")
        workflow_id = result["workflow_id"]
        state = get_workflow_state(workflow_id) or result
        _workflow_index[workflow_id] = state
        current_app.logger.info("Workflow completed successfully")
    except Exception as exc:
        error_trace = traceback.format_exc()
        current_app.logger.error(f"Workflow error: {exc}\n{error_trace}")
        print(f"WORKFLOW ERROR: {exc}\n{error_trace}")
        if _wants_json():
            return jsonify({"error": str(exc), "trace": error_trace}), 500
        return render_template(
            "base.html",
            **base_context(
                active_tab="langgraph",
                note_text=note,
                langgraph_error=f"{str(exc)}\n{error_trace}",
            ),
        ), 500

    if _wants_json():
        return jsonify(state), 201
    return render_template(
        "base.html",
        **base_context(
            active_tab="langgraph",
            note_text=note,
            langgraph_workflow=state,
            langgraph_pending=_pending_workflows(),
        ),
    )


@langgraph_bp.get("/pending")
def pending():
    workflows = _pending_workflows()
    if _wants_json():
        return jsonify({"pending": workflows, "count": len(workflows)})
    selected = None
    workflow_id = request.args.get("workflow_id")
    if workflow_id:
        selected = get_workflow_state(workflow_id)
    return render_template(
        "base.html",
        **base_context(
            active_tab="langgraph",
            langgraph_workflow=selected,
            langgraph_pending=workflows,
        ),
    )


@langgraph_bp.post("/approve")
def approve():
    payload = request.get_json(silent=True) or request.form
    workflow_id = str(payload.get("workflow_id") or "").strip()
    raw_indexes = payload.get("approved_indexes", [])
    if hasattr(payload, "getlist"):
        raw_indexes = payload.getlist("approved_indexes")
    elif not isinstance(raw_indexes, list):
        raw_indexes = [raw_indexes]

    if not workflow_id:
        message = "A workflow_id is required."
        if _wants_json():
            return jsonify({"error": message}), 400
        return render_template(
            "base.html",
            **base_context(active_tab="langgraph", langgraph_error=message),
        ), 400

    try:
        approved_indexes = [int(index) for index in raw_indexes if str(index).strip()]
        result = resume_workflow(workflow_id, approved_indexes)
        state = get_workflow_state(workflow_id) or result
        _workflow_index[workflow_id] = state
    except Exception as exc:
        if _wants_json():
            return jsonify({"error": str(exc)}), 500
        return render_template(
            "base.html",
            **base_context(
                active_tab="langgraph",
                langgraph_error=str(exc),
                langgraph_pending=_pending_workflows(),
            ),
        ), 500

    if _wants_json():
        return jsonify(state)
    return render_template(
        "base.html",
        **base_context(
            active_tab="langgraph",
            langgraph_workflow=state,
            langgraph_pending=_pending_workflows(),
        ),
    )
