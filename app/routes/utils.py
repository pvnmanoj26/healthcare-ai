from services.patients import get_patient_stats
from services.clinical_summary import GUIDELINES
from adapters.upstash import get_vector_count

def base_context(**kwargs):
    stats = get_patient_stats()
    defaults = dict(
        summary=None,
        gaps=None,
        guideline_count=len(GUIDELINES),
        notes_count=get_vector_count(),
        ingest_results=None,
        search_results=None,
        search_query=None,
        note_text=None,
        patient_id=None,
        patients=None,
        stats=stats,
        active_tab="summarize",
        ask_question=None,
        ask_answer=None,
        ask_sources=None,
    )
    defaults.update(kwargs)
    return defaults
