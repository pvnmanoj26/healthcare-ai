from typing import List, Optional
from pydantic import BaseModel, validator

class ClinicalSummary(BaseModel):
    out_of_scope:      bool          = False
    reason:            Optional[str] = None
    primary_diagnosis: str           = ""
    procedure:         Optional[str] = ""
    comorbidities:     List[str]     = []
    medications:       List[str]     = []
    key_findings:      List[str]     = []
    risk_flags:        List[str]     = []
    follow_up_actions: List[str]     = []

    @validator("medications", pre=True)
    def medications_must_be_list(cls, v):
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v

    @validator("comorbidities", "risk_flags", "key_findings",
               "follow_up_actions", pre=True)
    def lists_must_be_lists(cls, v):
        if isinstance(v, str):
            return [v] if v else []
        return v

    @validator("medications", each_item=True)
    def no_surgical_supplies(cls, v):
        surgical_keywords = [
            "monocryl", "nylon", "suture", "xylocaine", "lidocaine",
            "epinephrine", "silk", "vicryl", "prolene", "staple",
            "betadine", "chlorhexidine"
        ]
        for keyword in surgical_keywords:
            if keyword in v.lower():
                raise ValueError(f"Surgical supply in medications: {v}")
        return v

    @validator("comorbidities", each_item=True)
    def no_symptoms_as_comorbidities(cls, v):
        symptom_keywords = [
            "fatigue", "blurred vision", "nocturia", "polyuria",
            "polydipsia", "hemoptysis", "syncope", "dizziness",
            "shortness of breath", "chest pain", "nausea"
        ]
        for keyword in symptom_keywords:
            if keyword in v.lower():
                raise ValueError(f"Symptom in comorbidities: {v}")
        return v
