from __future__ import annotations
from datetime import date as Date
from typing import Any, Literal
from pydantic import BaseModel, Field
from models.events import ClinicalEvent
from models.ingestion import ClaimRow, ClaimTransactionRow, PayerTransitionRow, SupplyRow

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]
Gender = Literal["M", "F", "UNKNOWN"]

class PatientDemographics(BaseModel):
    patient_id: str
    first_name: str | None = None
    last_name: str | None = None
    birthdate: Date | None = None
    deathdate: Date | None = None
    gender: Gender = "UNKNOWN"
    race: str | None = None
    ethnicity: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None

class ClinicalPatientRecord(BaseModel):
    patient: PatientDemographics
    source: Literal["synthea_csv"] = "synthea_csv"
    risk_level: RiskLevel = "UNKNOWN"
    primary_diagnosis: str | None = None
    clinical_note: str | None = None
    allergies: list[ClinicalEvent] = Field(default_factory=list)
    careplans: list[ClinicalEvent] = Field(default_factory=list)
    claims: list[ClaimRow] = Field(default_factory=list)
    claim_transactions: list[ClaimTransactionRow] = Field(default_factory=list)
    conditions: list[ClinicalEvent] = Field(default_factory=list)
    devices: list[ClinicalEvent] = Field(default_factory=list)
    encounters: list[ClinicalEvent] = Field(default_factory=list)
    imaging_studies: list[ClinicalEvent] = Field(default_factory=list)
    immunizations: list[ClinicalEvent] = Field(default_factory=list)
    medications: list[ClinicalEvent] = Field(default_factory=list)
    observations: list[ClinicalEvent] = Field(default_factory=list)
    payer_transitions: list[PayerTransitionRow] = Field(default_factory=list)
    procedures: list[ClinicalEvent] = Field(default_factory=list)
    supplies: list[ClinicalEvent] = Field(default_factory=list)
    events: list[ClinicalEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
