from __future__ import annotations
import csv
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from datetime import date, datetime

from config.settings import ANTHROPIC_API_KEY
from adapters.anthropic import get_claude_response
from models import (
    ClinicalEvent,
    ClinicalPatientRecord,
    PatientDemographics,
    ColumnProfile,
)

_BASE_DIR = Path(__file__).resolve().parent.parent
MAPPINGS_DIR = _BASE_DIR / "config" / "mappings"
MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_SCHEMA = {
    "patient_id": "Stable patient identifier such as patient_id, member_id, MRN, or person_id.",
    "demographics.first_name": "Patient first or given name.",
    "demographics.last_name": "Patient last or family name.",
    "demographics.birth_date": "Patient date of birth.",
    "demographics.gender": "Patient administrative gender or sex.",
    "demographics.race": "Patient race.",
    "demographics.ethnicity": "Patient ethnicity.",
    "demographics.address": "Patient street address.",
    "demographics.city": "Patient city.",
    "demographics.state": "Patient state.",
    "demographics.zip_code": "Patient ZIP or postal code.",
    "event.event_type": "Clinical event category such as condition, medication, encounter, observation, procedure, allergy, immunization.",
    "event.code": "Clinical code such as SNOMED, LOINC, RxNorm, ICD, CPT, or internal code.",
    "event.description": "Human readable event description.",
    "event.start_date": "Event start, onset, authored, or service date.",
    "event.end_date": "Event end, stop, resolved, or discharge date.",
    "event.encounter_id": "Encounter, visit, or claim context identifier.",
    "event.status": "Clinical or workflow status.",
    "event.value": "Observation result, medication amount, claim amount, or other measured value.",
    "event.unit": "Unit for event.value.",
}

COMMON_ALIASES = {
    "patient_id": ["patient", "patient_id", "patientid", "person", "person_id", "member", "member_id", "mrn", "id"],
    "demographics.first_name": ["first", "firstname", "first_name", "given", "given_name"],
    "demographics.last_name": ["last", "lastname", "last_name", "family", "family_name", "surname"],
    "demographics.birth_date": ["birthdate", "birth_date", "date_of_birth", "dob", "birth"],
    "demographics.gender": ["gender", "sex"],
    "demographics.race": ["race"],
    "demographics.ethnicity": ["ethnicity"],
    "demographics.address": ["address", "street", "street_address"],
    "demographics.city": ["city"],
    "demographics.state": ["state"],
    "demographics.zip_code": ["zip", "zipcode", "zip_code", "postal", "postal_code"],
    "event.event_type": ["type", "category", "event_type", "class"],
    "event.code": ["code", "snomed", "loinc", "rxnorm", "icd", "cpt", "diagnosis_code", "procedure_code"],
    "event.description": ["description", "desc", "name", "reason", "display", "text"],
    "event.start_date": ["start", "start_date", "date", "onset", "from", "service_date", "authoredon"],
    "event.end_date": ["stop", "end", "end_date", "resolved", "to", "discharge_date"],
}

def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower().strip())

def clean_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def parse_date(value: Any) -> date | datetime | None:
    text = clean_value(value)
    if not text:
        return None
    formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(text[:19], fmt)
            return parsed if "H" in fmt else parsed.date()
        except ValueError:
            continue
    return None

def detect_value_type(value: str) -> str:
    if parse_date(value):
        return "date"
    if re.fullmatch(r"-?\d+", value):
        return "integer"
    if re.fullmatch(r"-?\d+\.\d+", value):
        return "decimal"
    if value.lower() in {"true", "false", "yes", "no", "y", "n"}:
        return "boolean"
    return "text"

def semantic_hints(values: list[str]) -> list[str]:
    joined = " ".join(values[:30]).lower()
    hints: list[str] = []
    if any(k in joined for k in ["snomed", "loinc", "rxnorm", "icd"]):
        hints.append("clinical_code_system")
    return hints

def profile_csv_file(csv_path: str | Path, sample_size: int = 50) -> dict[str, Any]:
    csv_path = Path(csv_path)
    sampled_rows: list[dict[str, str]] = []
    column_values: dict[str, list[str]] = defaultdict(list)
    null_counts: Counter[str] = Counter()

    with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames or []

        for row_index, row in enumerate(reader):
            if row_index < sample_size:
                sampled_rows.append(row)
            for column in columns:
                value = clean_value(row.get(column))
                if value is None:
                    null_counts[column] += 1
                elif len(column_values[column]) < sample_size:
                    column_values[column].append(value)
            if row_index + 1 >= sample_size:
                break

    profiles = []
    for column in columns:
        values = column_values[column]
        type_counts = Counter(detect_value_type(v) for v in values)
        profiles.append(
            ColumnProfile(
                name=column,
                normalized_name=normalize_name(column),
                non_null_count=len(values),
                null_count=null_counts[column],
                distinct_count=len(set(values)),
                sample_values=values[:10],
                detected_types=[name for name, _ in type_counts.most_common()],
                semantic_hints=semantic_hints(values),
            ).__dict__
        )

    return {
        "file_name": csv_path.name,
        "path": str(csv_path),
        "sample_size": len(sampled_rows),
        "columns": profiles,
        "target_schema": TARGET_SCHEMA,
    }

def fuzzy_score(source_name: str, aliases: list[str]) -> float:
    source = normalize_name(source_name)
    return max(SequenceMatcher(None, source, normalize_name(alias)).ratio() for alias in aliases)

def propose_mapping_with_rules(profile: dict[str, Any]) -> dict[str, Any]:
    mappings = []
    for column in profile["columns"]:
        best_target = None
        best_score = 0.0
        for target, aliases in COMMON_ALIASES.items():
            score = fuzzy_score(column["name"], aliases)
            if score > best_score:
                best_target = target
                best_score = score

        if best_target and best_score >= 0.82:
            confidence = round(best_score, 2)
            reason = "Column name closely matches known aliases."
        else:
            best_target = None
            confidence = 0.0
            reason = "No reliable rule-based match."

        mappings.append({
            "source_column": column["name"],
            "target_field": best_target,
            "confidence": confidence,
            "requires_review": confidence < 0.9,
            "reason": reason,
            "sample_values": column["sample_values"][:5],
            "semantic_hints": column["semantic_hints"],
        })
    return {
        "file_name": profile["file_name"],
        "mapping_source": "rules",
        "mappings": mappings,
    }

def propose_mapping_with_ai(profile: dict[str, Any], model: str | None = None) -> dict[str, Any]:
    if not ANTHROPIC_API_KEY:
        proposal = propose_mapping_with_rules(profile)
        proposal["mapping_source"] = "rules_no_anthropic_key"
        return proposal

    system_prompt = """You are a healthcare data ingestion mapping assistant.
You map messy source CSV columns into a canonical clinical data model.
Always respond with valid JSON only. No markdown. No explanation outside JSON."""

    user_prompt = f"""
Map each source CSV column to the best target field from TARGET_SCHEMA.
Use both column names and sample values. Do not guess when ambiguous.

Return only valid JSON with this shape:
{{
  "file_name": "...",
  "mapping_source": "ai",
  "mappings": [
    {{
      "source_column": "...",
      "target_field": "patient_id | demographics.first_name | event.code | null",
      "confidence": 0.0,
      "requires_review": true,
      "reason": "short explanation",
      "sample_values": ["..."],
      "semantic_hints": ["..."]
    }}
  ],
  "warnings": ["..."]
}}

Rules:
- If a column is ambiguous, use null for target_field.
- Set requires_review=true for confidence below 0.90.
- Use sample values to distinguish patient identifiers.
- Never invent target fields outside TARGET_SCHEMA.

TARGET_SCHEMA:
{json.dumps(TARGET_SCHEMA, indent=2)}

CSV_PROFILE:
{json.dumps(profile, indent=2)}
"""
    try:
        text = get_claude_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.0,
            model=model,
        )
    except Exception as exc:
        proposal = propose_mapping_with_rules(profile)
        proposal["mapping_source"] = "rules_claude_error"
        proposal["claude_error"] = str(exc)
        return proposal

    from services.clinical_summary import clean_json
    text = clean_json(text)
    try:
        proposal = json.loads(text)
    except json.JSONDecodeError:
        proposal = propose_mapping_with_rules(profile)
        proposal["mapping_source"] = "rules_ai_invalid_json"
        return proposal

    proposal["mapping_source"] = proposal.get("mapping_source") or "ai"
    return proposal

def mapping_path(file_name: str, mappings_dir: str | Path | None = None) -> Path:
    mappings_dir = Path(mappings_dir) if mappings_dir else MAPPINGS_DIR
    mappings_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file_name).name.replace(".csv", "")
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", safe_name)
    return mappings_dir / f"{safe_name}.mapping.json"

def save_mapping(mapping: dict[str, Any], output_path: str | Path | None = None, mappings_dir: str | Path | None = None) -> Path:
    if output_path is None:
        output_path = mapping_path(mapping.get("file_name", "mapping"), mappings_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    return output_path

def load_mapping(mapping_file: str | Path) -> dict[str, Any]:
    mapping_file = Path(mapping_file)
    if not mapping_file.exists():
        mapping_file = MAPPINGS_DIR / mapping_file.name
    return json.loads(mapping_file.read_text(encoding="utf-8"))

def mapping_preview_markdown(mapping: dict[str, Any]) -> str:
    lines = [
        f"# Mapping Preview: {mapping.get('file_name', 'unknown')}",
        "",
        "| Source Column | Target Field | Confidence | Review? | Sample Values | Reason |",
        "|---|---|---:|---|---|---|",
    ]
    for item in mapping.get("mappings", []):
        samples = ", ".join(str(v) for v in item.get("sample_values", [])[:3])
        review = "YES" if item.get("requires_review") else "NO"
        lines.append(
            "| {source} | {target} | {confidence} | {review} | {samples} | {reason} |".format(
                source=item.get("source_column", ""),
                target=item.get("target_field") or "UNMAPPED",
                confidence=item.get("confidence", 0),
                review=review,
                samples=samples.replace("|", "/"),
                reason=str(item.get("reason", "")).replace("|", "/"),
            )
        )
    return "\n".join(lines)

def ensure_approved(mapping: dict[str, Any]) -> None:
    if not mapping.get("approved"):
        raise ValueError("Mapping is not approved. Set 'approved': true before ingestion.")

def model_fields(model_cls: type) -> set[str]:
    return set(getattr(model_cls, "model_fields", {}).keys())

def make_patient_record(patient_id: str) -> ClinicalPatientRecord:
    return ClinicalPatientRecord(patient=PatientDemographics(patient_id=patient_id))

def apply_demographic(record: ClinicalPatientRecord, field: str, value: Any) -> None:
    demographics = record.patient
    demo_field = field.split(".", 1)[1]
    field_mapping = {"birth_date": "birthdate", "zip_code": "zip"}
    target_attr = field_mapping.get(demo_field, demo_field)

    if target_attr == "birthdate":
        value = parse_date(value)
    elif target_attr == "gender":
        if value:
            norm_val = str(value).strip().upper()
            if norm_val in {"M", "F"}:
                value = norm_val
            elif norm_val == "MALE":
                value = "M"
            elif norm_val == "FEMALE":
                value = "F"
            else:
                value = "UNKNOWN"
        else:
            value = "UNKNOWN"

    if hasattr(demographics, target_attr):
        setattr(demographics, target_attr, value)

def make_event(values: dict[str, Any], raw: dict[str, Any], file_name: str) -> ClinicalEvent:
    event_values = {"source_file": file_name, "metadata": raw}
    field_mapping = {"start_date": "start", "end_date": "stop"}
    for field, value in values.items():
        event_field = field.split(".", 1)[1]
        target_field = field_mapping.get(event_field, event_field)
        if target_field in {"start", "stop"}:
            value = parse_date(value)
        event_values[target_field] = value

    if "description" not in event_values or event_values["description"] is None:
        event_values["description"] = event_values.get("code") or "Unknown Event"

    allowed = model_fields(ClinicalEvent)
    return ClinicalEvent(**{k: v for k, v in event_values.items() if k in allowed and v is not None})

def attach_event(record: ClinicalPatientRecord, event: ClinicalEvent, event_type: str) -> None:
    from adapters.bigquery import EVENT_TYPE_TO_FIELD
    key = str(event_type).strip().lower()
    field_name = EVENT_TYPE_TO_FIELD.get(key, "events")
    if hasattr(record, field_name):
        getattr(record, field_name).append(event)

def ingest_csv_with_mapping(csv_path: str | Path, mapping: dict[str, Any]) -> list[ClinicalPatientRecord]:
    ensure_approved(mapping)
    csv_path = Path(csv_path)
    mapped_fields = {
        item["source_column"]: item["target_field"]
        for item in mapping.get("mappings", [])
        if item.get("target_field")
    }

    records: dict[str, ClinicalPatientRecord] = {}
    with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=1):
            patient_id = None
            event_values: dict[str, Any] = {}

            for source_column, target_field in mapped_fields.items():
                value = clean_value(row.get(source_column))
                if value is None:
                    continue
                if target_field == "patient_id":
                    patient_id = value
                elif target_field.startswith("event."):
                    event_values[target_field] = value

            if not patient_id:
                patient_id = f"{csv_path.stem}_row_{row_number}"

            record = records.setdefault(patient_id, make_patient_record(patient_id))
            for source_column, target_field in mapped_fields.items():
                value = clean_value(row.get(source_column))
                if value is None:
                    continue
                if target_field.startswith("demographics."):
                    apply_demographic(record, target_field, value)

            if event_values:
                event_type = event_values.get("event.event_type") or csv_path.stem
                event = make_event(event_values, dict(row), csv_path.name)
                attach_event(record, event, event_type)

    return list(records.values())
