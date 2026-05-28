import json
import re
import numpy as np
import faiss
from adapters.vertex_ai import get_embedding
from adapters.anthropic import get_claude_response
from models import ClinicalSummary, CareGapResult

# ── STATIC CLINICAL GUIDELINES ─────────────────────────
GUIDELINES = [
    # ── DIABETES ──────────────────────────────
    {"condition": "diabetes", "text": "Diabetes: HbA1c should be measured every 3 months if uncontrolled (>8%), every 6 months if stable."},
    {"condition": "diabetes", "text": "Diabetes: Annual diabetic eye exam (fundoscopy/retinal screening) is required for all diabetic patients."},
    {"condition": "diabetes", "text": "Diabetes: Annual diabetic foot exam including monofilament sensation test is required."},
    {"condition": "diabetes", "text": "Diabetes: Urine microalbumin/creatinine ratio should be checked annually to screen for nephropathy."},
    {"condition": "diabetes", "text": "Diabetes: Blood pressure target for diabetic patients is <130/80 mmHg."},
    {"condition": "diabetes", "text": "Diabetes: Statin therapy is recommended for all diabetic patients aged 40-75."},
    {"condition": "diabetes", "text": "Diabetes: ACE inhibitor or ARB is recommended if microalbuminuria is present."},
    {"condition": "diabetes", "text": "Diabetes: Referral to endocrinology if HbA1c remains >9% despite treatment."},
    {"condition": "diabetes", "text": "Diabetes: Diabetes self-management education program enrollment is recommended at diagnosis."},
    {"condition": "diabetes", "text": "Diabetes: Annual flu vaccination is recommended for all diabetic patients."},
    {"condition": "diabetes", "text": "Diabetes: Pneumococcal vaccination recommended for all diabetic patients."},

    # ── HEART FAILURE ──────────────────────────
    {"condition": "heart_failure", "text": "Heart Failure: ACE inhibitor or ARB therapy is recommended for all HFrEF patients (EF <40%)."},
    {"condition": "heart_failure", "text": "Heart Failure: Beta-blocker therapy is recommended for all stable HFrEF patients."},
    {"condition": "heart_failure", "text": "Heart Failure: Aldosterone antagonist recommended for HFrEF patients with EF <35%."},
    {"condition": "heart_failure", "text": "Heart Failure: BNP or NT-proBNP should be measured to assess disease severity."},
    {"condition": "heart_failure", "text": "Heart Failure: Echocardiogram recommended to assess ejection fraction at diagnosis and after treatment changes."},
    {"condition": "heart_failure", "text": "Heart Failure: Daily weight monitoring and fluid restriction education is required."},
    {"condition": "heart_failure", "text": "Heart Failure: Cardiology referral is recommended for newly diagnosed heart failure."},
    {"condition": "heart_failure", "text": "Heart Failure: Annual flu and pneumococcal vaccination recommended for heart failure patients."},
    {"condition": "heart_failure", "text": "Heart Failure: Sodium restriction to <2g/day is recommended."},
    {"condition": "heart_failure", "text": "Heart Failure: 30-day readmission follow-up appointment is required post-discharge."},

    # ── HYPERTENSION ──────────────────────────
    {"condition": "hypertension", "text": "Hypertension: Blood pressure target is <130/80 mmHg for most patients per ACC/AHA guidelines."},
    {"condition": "hypertension", "text": "Hypertension: If blood pressure is above target despite medication, intensify antihypertensive therapy or add a second agent."},
    {"condition": "hypertension", "text": "Hypertension: First-line agents include thiazide diuretics, CCBs, ACE inhibitors, or ARBs."},
    {"condition": "hypertension", "text": "Hypertension: Annual renal function (eGFR, creatinine) and electrolyte monitoring required."},
    {"condition": "hypertension", "text": "Hypertension: Lifestyle modifications including DASH diet and exercise counseling are required."},
    {"condition": "hypertension", "text": "Hypertension: EKG recommended to assess for LVH in newly diagnosed hypertensive patients."},
    {"condition": "hypertension", "text": "Hypertension: Cardiovascular risk assessment (10-year ASCVD risk) should be calculated and documented."},

    # ── CKD ───────────────────────────────────
    {"condition": "ckd", "text": "CKD: eGFR and urine albumin-creatinine ratio should be monitored every 3-6 months."},
    {"condition": "ckd", "text": "CKD: Blood pressure target for CKD patients is <130/80 mmHg."},
    {"condition": "ckd", "text": "CKD: ACE inhibitor or ARB recommended for CKD patients with proteinuria."},
    {"condition": "ckd", "text": "CKD: Nephrology referral recommended when eGFR falls below 30 mL/min."},
    {"condition": "ckd", "text": "CKD: Anemia workup (CBC, iron studies, ESA consideration) recommended for CKD patients."},
    {"condition": "ckd", "text": "CKD: Dietary protein restriction and phosphate management counseling recommended."},
    {"condition": "ckd", "text": "CKD: Avoid NSAIDs, aminoglycosides, and nephrotoxic contrast agents — document counseling."},
    {"condition": "ckd", "text": "CKD: Secondary hyperparathyroidism — monitor PTH every 3-6 months in stage III-V CKD."},
    {"condition": "ckd", "text": "CKD: Hepatitis B vaccination recommended for all CKD patients not yet immune."},
    {"condition": "ckd", "text": "CKD: Flu and pneumococcal vaccination recommended for all CKD patients."},

    # ── ASTHMA ────────────────────────────────
    {"condition": "asthma", "text": "Asthma: Annual spirometry/pulmonary function test recommended to assess control."},
    {"condition": "asthma", "text": "Asthma: Inhaled corticosteroid is first-line controller therapy for persistent asthma."},
    {"condition": "asthma", "text": "Asthma: Asthma action plan should be documented and provided to patient."},
    {"condition": "asthma", "text": "Asthma: Referral to pulmonology if symptoms uncontrolled on moderate-dose ICS."},

    # ── DYSLIPIDAEMIA ─────────────────────────
    {"condition": "dyslipidaemia", "text": "Dyslipidaemia: Fasting lipid panel should be checked annually."},
    {"condition": "dyslipidaemia", "text": "Dyslipidaemia: Statin therapy recommended for patients with cardiovascular risk >10% (10-year ASCVD risk)."},
    {"condition": "dyslipidaemia", "text": "Dyslipidaemia: LDL target <70 mg/dL for very high cardiovascular risk patients."},
    {"condition": "dyslipidaemia", "text": "Dyslipidaemia: Lifestyle counseling on diet and exercise is required alongside pharmacotherapy."},

    # ── GENERAL / PREVENTIVE ──────────────────
    {"condition": "general", "text": "General: Smoking cessation counseling and pharmacotherapy is strongly recommended for all active smokers at every clinical encounter."},
    {"condition": "general", "text": "General: Annual influenza vaccination recommended for all patients with chronic conditions."},
    {"condition": "general", "text": "General: Pneumococcal vaccination (PCV15/PPSV23) recommended for immunocompromised patients and those with chronic disease."},
    {"condition": "general", "text": "General: BMI should be documented and obesity management counseling provided if BMI >30."},
]

GUIDELINE_TEXTS      = [g["text"] for g in GUIDELINES]
GUIDELINE_CONDITIONS = [g["condition"] for g in GUIDELINES]

_guideline_index = None

def _ensure_guidelines_indexed():
    global _guideline_index
    if _guideline_index is None:
        print("Embedding clinical guidelines knowledge base...")
        from adapters.vertex_ai import get_embedding
        try:
            # Batch request embeddings
            from adapters.vertex_ai import _ensure_initialized, _embedder
            _ensure_initialized()
            result = _embedder.get_embeddings(GUIDELINE_TEXTS)
            guideline_embeddings = np.array([r.values for r in result], dtype="float32")
        except Exception as e:
            print(f"⚠️ Batched embedding failed: {e}. Falling back to sequential...")
            guideline_embeddings = np.array(
                [get_embedding(g) for g in GUIDELINE_TEXTS], dtype="float32"
            )
        _guideline_index = faiss.IndexFlatL2(guideline_embeddings.shape[1])
        _guideline_index.add(guideline_embeddings)
        print(f"✅ {len(GUIDELINES)} guidelines indexed.")

def chunk_text(text: str, chunk_size: int = 512) -> list[str]:
    words = text.split()
    approx_words = int(chunk_size / 1.3)
    if len(words) <= approx_words:
        return [text]
    return [
        " ".join(words[i:i+approx_words])
        for i in range(0, len(words), approx_words)
    ]

CONDITION_MAP = {
    "diabetes":           "diabetes",
    "diabetic":           "diabetes",
    "hyperglycemia":      "diabetes",
    "hba1c":              "diabetes",
    "heart failure":      "heart_failure",
    "chf":                "heart_failure",
    "cardiomyopathy":     "heart_failure",
    "hfref":              "heart_failure",
    "hypertension":       "hypertension",
    "high blood pressure":"hypertension",
    "ckd":                "ckd",
    "chronic kidney":     "ckd",
    "renal insufficiency":"ckd",
    "nephropathy":        "ckd",
    "kidney disease":     "ckd",
    "asthma":             "asthma",
    "dyslipidemia":       "dyslipidaemia",
    "dyslipidaemia":      "dyslipidaemia",
    "hyperlipidemia":     "dyslipidaemia",
    "cholesterol":        "dyslipidaemia",
}

def detect_conditions(summary: dict) -> set[str]:
    detected = set(["general"])
    search_text = summary.get("primary_diagnosis", "").lower()
    for c in summary.get("comorbidities", []):
        search_text += " " + c.lower()
    for keyword, tag in CONDITION_MAP.items():
        if keyword in search_text:
            detected.add(tag)
    return detected

def retrieve_relevant_guidelines(query: str, summary: dict | None = None, k: int = 12) -> list[str]:
    _ensure_guidelines_indexed()
    query_vec = np.array([get_embedding(query)], dtype="float32")
    D, I = _guideline_index.search(query_vec, k=min(k*2, len(GUIDELINES)))

    if summary:
        detected_conditions = detect_conditions(summary)
        filtered = []
        for idx in I[0]:
            guideline_condition = GUIDELINE_CONDITIONS[idx]
            if guideline_condition in detected_conditions:
                filtered.append(GUIDELINE_TEXTS[idx])
            if len(filtered) >= k:
                break
        if len(filtered) < 3:
            for idx in I[0]:
                if GUIDELINE_TEXTS[idx] not in filtered:
                    filtered.append(GUIDELINE_TEXTS[idx])
                if len(filtered) >= k:
                    break
        return filtered
    else:
        return [GUIDELINE_TEXTS[i] for i in I[0][:k]]

def clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def generate_clinical_summary(note: str, temperature: float = 0.0, max_tokens: int = 1500) -> ClinicalSummary:
    system_prompt = (
        "You are an expert clinical summariser. Output valid, parsed JSON matching this structure: "
        '{"out_of_scope": bool, "reason": str or null, "primary_diagnosis": str, "procedure": str, '
        '"comorbidities": [str], "medications": [str], "key_findings": [str], "risk_flags": [str], "follow_up_actions": [str]}. '
        "Extract only facts present in the note. Do not list symptoms as comorbidities. Do not list surgical supplies as medications."
    )
    raw_json = get_claude_response(system_prompt, note, max_tokens=max_tokens, temperature=temperature)
    cleaned = clean_json(raw_json)
    summary_dict = json.loads(cleaned)
    return ClinicalSummary(**summary_dict)

def analyze_care_gaps(note: str, temperature: float = 0.0, max_tokens: int = 1500) -> CareGapResult:
    # Determine conditions for guideline retrieval
    temp_summary = {"primary_diagnosis": note, "comorbidities": []}
    guidelines = retrieve_relevant_guidelines(note, temp_summary, k=10)
    guidelines_context = "\n".join([f"- {g}" for g in guidelines])

    system_prompt = (
        "You are a clinical care gap analyst. Compare the patient note against these guidelines:\n"
        f"{guidelines_context}\n\n"
        "Output valid JSON matching this schema: "
        '{"gaps": [{"gap": "string", "guideline": "string", "recommendation": "string", "priority": "HIGH|MEDIUM|LOW"}], '
        '"summary": "string"}. Only output gaps that are explicitly indicated as missing/incomplete in the note.'
    )
    raw_json = get_claude_response(system_prompt, note, max_tokens=max_tokens, temperature=temperature)
    cleaned = clean_json(raw_json)
    result_dict = json.loads(cleaned)
    return CareGapResult(**result_dict)

def search_notes(query: str, top_k: int = 5) -> list:
    """
    Search indexed clinical notes semantically using Upstash.
    Returns a list of tuples: (text_chunk, metadata)
    """
    from adapters.upstash import query_vectors
    from adapters.vertex_ai import get_embedding

    query_vec = get_embedding(query)
    results = query_vectors(query_vec, top_k=top_k)
    if not results:
        return []
    return [(r.data or "", r.metadata) for r in results]

def ask_clinical_question(question: str) -> dict:
    """
    Ask a clinical question using RAG over indexed notes chunks.
    """
    chunks = search_notes(question, top_k=5)
    if not chunks:
        return {
            "answer": "I couldn't find any relevant clinical notes in the system to answer your question.",
            "sources": [],
            "chunks": []
        }

    context_str = ""
    sources = []
    seen_urls = {}
    source_counter = 1

    for doc, meta in chunks:
        url = meta.get("url", "Unknown Source")
        if url not in seen_urls:
            seen_urls[url] = source_counter
            sources.append((source_counter, url))
            source_counter += 1
        num = seen_urls[url]
        context_str += f"\n[Source {num}]: {doc}\n"

    system_prompt = (
        "You are a clinical Q&A assistant. Answer the user's question accurately using only the provided notes chunks.\n"
        "Cite the Source numbers (e.g. [Source 1]) in your answer where appropriate. If the context does not contain the answer, "
        "say 'I cannot find that information in the clinical notes.'"
    )

    user_prompt = f"Context clinical chunks:\n{context_str}\n\nQuestion: {question}"
    answer = get_claude_response(system_prompt, user_prompt, max_tokens=1500, temperature=0.0)

    return {
        "answer": answer,
        "sources": sources,
        "chunks": chunks
    }
