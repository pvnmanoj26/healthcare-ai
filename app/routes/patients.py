from flask import Blueprint, request, render_template
from app.routes.utils import base_context
from services.patients import get_all_patients, get_patients_by_risk, get_patient_by_id

patients_bp = Blueprint("patients", __name__)

@patients_bp.route("/")
@patients_bp.route("/patients")
def patients_list():
    risk = request.args.get("risk")
    if risk:
        patients = get_patients_by_risk(risk.upper())
    else:
        patients = get_all_patients()
    return render_template("base.html", **base_context(patients=patients, active_tab="patients"))

@patients_bp.route("/patient/<patient_id>")
def patient_detail(patient_id):
    patient = get_patient_by_id(patient_id)
    if not patient:
        return "Patient not found", 404
        
    import json
    for field in ["comorbidities", "medications", "key_findings", "risk_flags", "follow_up_actions"]:
        if patient.get(field):
            try:
                patient[field] = json.loads(patient[field])
            except Exception:
                patient[field] = []
    return render_template("patient_detail.html", patient=patient)
