from __future__ import annotations
from datetime import date as Date, datetime as DateTime
from typing import Any
from pydantic import BaseModel, Field

class ClinicalEvent(BaseModel):
    source_file: str
    source_id: str | None = None
    encounter_id: str | None = None
    code: str | None = None
    description: str
    start: Date | DateTime | None = None
    stop: Date | DateTime | None = None
    status: str | None = None
    value: str | None = None
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
