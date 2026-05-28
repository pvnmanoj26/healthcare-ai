from typing import List
from pydantic import BaseModel, validator

class CareGap(BaseModel):
    gap:            str
    guideline:      str
    recommendation: str
    priority:       str = "MEDIUM"

    @validator("priority")
    def priority_must_be_valid(cls, v):
        if v.upper() not in {"HIGH", "MEDIUM", "LOW"}:
            return "MEDIUM"
        return v.upper()

class CareGapResult(BaseModel):
    gaps:    List[CareGap] = []
    summary: str           = ""
