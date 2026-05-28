from adapters.cloud_run import _request

def _is_error(result: dict) -> bool:
    return isinstance(result, dict) and "error" in result

def _safe_limit(limit: int, default: int = 5, maximum: int = 10) -> int:
    try:
        return min(max(int(limit), 1), maximum)
    except (TypeError, ValueError):
        return default

def list_patients(risk_level: str = None, limit: int = 10) -> dict:
    """
    List patients from BigQuery.
    Optionally filter by risk_level: HIGH, MEDIUM, or LOW.
    Returns patient IDs and diagnoses without clinical notes.
    """
    params = {"limit": _safe_limit(limit, default=10)}
    if risk_level:
        params["risk_level"] = risk_level.upper()
    patients = _request("GET", "/patients", params=params)
    if _is_error(patients):
        return patients
    if isinstance(patients, dict):
        patients = patients.get("patients", patients)
    if isinstance(patients, list):
        for p in patients:
            p.pop("source_note", None)
    return {"patients": patients}

def get_population_gaps(risk_level: str = "HIGH", limit: int = 5) -> dict:
    """
    Get care gaps for multiple patients at once.
    Prefer this over analyzing patients one by one.
    Returns prioritised gaps sorted by severity.
    """
    params = {"limit": _safe_limit(limit)}
    if risk_level:
        params["risk_level"] = risk_level.upper()
    patients = _request("GET", "/patients", params=params)

    if _is_error(patients):
        return patients

    if isinstance(patients, dict):
        patients = patients.get("patients", [])

    results = []
    errors = []
    for p in patients:
        pid = p.get("patient_id")
        if not pid:
            continue
        full = _request("GET", f"/patients/{pid}")
        if _is_error(full):
            errors.append({"patient_id": pid, **full})
            continue
        note = full.get("source_note", "")
        if not note:
            continue
        gaps = _request("POST", "/caregaps", json={"note": note})
        if _is_error(gaps):
            errors.append({"patient_id": pid, **gaps})
            continue
        results.append({
            "patient_id":        pid,
            "primary_diagnosis": p.get("primary_diagnosis", ""),
            "risk_level":        p.get("risk_level", ""),
            "gap_count":         len(gaps.get("gaps", [])),
            "gaps":              gaps.get("gaps", []),
            "summary":           gaps.get("summary", "")
        })

    results.sort(key=lambda x: x["gap_count"], reverse=True)
    return {
        "population_gaps": results,
        "total_patients":  len(results),
        "total_gaps":      sum(r["gap_count"] for r in results),
        "errors":          errors,
        "critical_gaps":   sum(
            1 for r in results
            for g in r["gaps"]
            if g.get("priority") == "HIGH"
        )
    }
