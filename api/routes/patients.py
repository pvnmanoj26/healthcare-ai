from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from services.patients import get_all_patients, get_patients_by_risk, get_patient_by_id

router = APIRouter(prefix="/patients", tags=["patients"])

class PatientRecord(BaseModel):
    patient_id:        str
    primary_diagnosis: str
    risk_level:        str
    created_at:        str
    comorbidities:     Optional[str] = None
    medications:       Optional[str] = None
    risk_flags:        Optional[str] = None

@router.get("", response_model=List[PatientRecord])
def get_patients(risk_level: Optional[str] = None, limit: int = 50):
    if risk_level:
        rows = get_patients_by_risk(risk_level.upper())
    else:
        rows = get_all_patients()
    return rows[:limit]

@router.get("/{patient_id}", response_model=PatientRecord)
def get_patient(patient_id: str):
    row = get_patient_by_id(patient_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return row
