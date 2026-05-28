from flask import Blueprint, request, render_template
from app.routes.utils import base_context
from services.clinical_summary import generate_clinical_summary, analyze_care_gaps
from services.patients import save_patient

summarizer_bp = Blueprint("summarizer", __name__)

@summarizer_bp.route("/summarize", methods=["POST"])
def run_summarizer():
    note = request.form.get("clinical_note", "")
    temp = float(request.form.get("temperature", 0.0))
    max_t = int(request.form.get("max_tokens", 1500))

    if not note.strip():
        return render_template("base.html", **base_context(note_text=note))

    try:
        validated = generate_clinical_summary(note, temperature=temp, max_tokens=max_t)
    except Exception as e:
        print(f"Validation failed: {e}")
        return render_template("base.html", **base_context(note_text=note, out_of_scope_reason=f"Failed validation: {e}"))

    if validated.out_of_scope:
        return render_template("base.html", **base_context(note_text=note, out_of_scope_reason=validated.reason))

    patient_id = save_patient(validated.model_dump(), note)
    return render_template("base.html", **base_context(summary=validated.model_dump(), patient_id=patient_id, note_text=note))

@summarizer_bp.route("/caregaps", methods=["POST"])
def run_caregaps():
    note = request.form.get("clinical_note", "")
    temp = float(request.form.get("temperature", 0.0))
    max_t = int(request.form.get("max_tokens", 1500))

    if not note.strip():
        return render_template("base.html", **base_context(note_text=note, active_tab="gaps"))

    try:
        validated = analyze_care_gaps(note, temperature=temp, max_tokens=max_t)
    except Exception as e:
        return render_template("base.html", **base_context(note_text=note, active_tab="gaps", out_of_scope_reason=f"Parsing error: {e}"))

    return render_template("base.html", **base_context(gaps=validated.model_dump(), note_text=note, active_tab="gaps"))
