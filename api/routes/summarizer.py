from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from services.clinical_summary import generate_clinical_summary, analyze_care_gaps
from services.patients import save_patient
from adapters.upstash import upsert_vectors
from adapters.vertex_ai import get_embedding

router = APIRouter(tags=["summarizer"])

class NoteRequest(BaseModel):
    note:       str
    max_tokens: Optional[int] = 1500

class SummaryResponse(BaseModel):
    patient_id:        Optional[str] = None
    primary_diagnosis: str           = ""
    comorbidities:     List[str]     = []
    medications:       List[str]     = []
    key_findings:      List[str]     = []
    risk_flags:        List[str]     = []
    follow_up_actions: List[str]     = []
    risk_level:        str           = "LOW"
    out_of_scope:      bool          = False
    reason:            Optional[str] = None

class CareGap(BaseModel):
    gap:            str
    guideline:      str
    recommendation: str
    priority:       str = "MEDIUM"

class CareGapsResponse(BaseModel):
    gaps:    List[CareGap] = []
    summary: str           = ""

@router.post("/summarize", response_model=SummaryResponse)
def summarize(req: NoteRequest):
    try:
        data = generate_clinical_summary(req.note, max_tokens=req.max_tokens)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Summarization validation failed: {e}")

    if data.out_of_scope:
        return SummaryResponse(out_of_scope=True, reason=data.reason)

    flag_count = len(data.risk_flags)
    risk_level = "HIGH" if flag_count >= 3 else "MEDIUM" if flag_count >= 1 else "LOW"
    patient_id = save_patient(data.model_dump(), req.note)

    try:
        upsert_vectors([{
            "id":       f"patient_{patient_id}",
            "vector":   get_embedding(req.note),
            "data":     req.note,
            "metadata": {
                "patient_id":        patient_id,
                "primary_diagnosis": data.primary_diagnosis,
                "risk_level":        risk_level,
                "url":               "api_entry",
                "chunk":             0
            }
        }])
    except Exception as e:
        print(f"Failed to upsert to vector index: {e}")

    return SummaryResponse(
        patient_id=patient_id,
        primary_diagnosis=data.primary_diagnosis,
        comorbidities=data.comorbidities,
        medications=data.medications,
        key_findings=data.key_findings,
        risk_flags=data.risk_flags,
        follow_up_actions=data.follow_up_actions,
        risk_level=risk_level
    )

@router.post("/caregaps", response_model=CareGapsResponse)
def caregaps(req: NoteRequest):
    try:
        data = analyze_care_gaps(req.note, max_tokens=req.max_tokens)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Care gap analysis failed: {e}")

    return CareGapsResponse(
        gaps=[CareGap(**g.model_dump()) for g in data.gaps],
        summary=data.summary
    )
