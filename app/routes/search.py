import asyncio
import re
import httpx
from bs4 import BeautifulSoup
from flask import Blueprint, request, render_template
from app.routes.utils import base_context
from services.clinical_summary import search_notes, ask_clinical_question, chunk_text, generate_clinical_summary
from adapters.upstash import upsert_vectors
from adapters.vertex_ai import get_embedding
from services.patients import save_patient

search_bp = Blueprint("search", __name__)

async def scrape_url_async(client, url):
    try:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        main = soup.select_one("div.col-lg-9.mainContent")
        if main:
            text = main.get_text(separator=" ").strip()
            text = re.sub(r"\s+", " ", text)
            match = re.search(r"Sample Name:", text)
            if not match:
                match = re.search(
                    r"(REASON FOR VISIT|CHIEF COMPLAINT|HISTORY OF PRESENT ILLNESS|"
                    r"SUBJECTIVE|PREOPERATIVE DIAGNOSIS|ADMISSION DIAGNOSIS|"
                    r"CONSULTATION|DISCHARGE SUMMARY|PROCEDURE)", text
                )
            if match:
                text = text[match.start():]
            noise = [
                "Intended for: Medical transcription students, transcriptionists, and educators practicing clinical documentation formats in General Medicine.",
                "Discover more", "Newspapers", "News",
                "Secure transcription solutions", "Medical transcription software",
                "Nasal Sprays", "Drugs & Medications", "Health Conditions",
            ]
            for n in noise:
                text = text.replace(n, "")
            for stop in ["About This Sample:", "Legal & Usage Notice",
                         "Related Samples", "Keywords:", "Go Back to"]:
                if stop in text:
                    text = text[:text.index(stop)]
                    break
            text = re.sub(r"\s+", " ", text).strip()
            if len(text.split()) > 50:
                return text
    except Exception:
        pass
    return None

async def scrape_multiple_urls(urls):
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True
    ) as client:
        tasks = [scrape_url_async(client, url) for url in urls]
        results = await asyncio.gather(*tasks)
    return results

def index_note(url, text, patient_id=None):
    chunks = chunk_text(text, chunk_size=512)
    vectors = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{abs(hash(url))}_{i}"
        embedding = get_embedding(chunk)
        vectors.append({
            "id":       chunk_id,
            "vector":   embedding,
            "data":     chunk,
            "metadata": {"url": url, "chunk": i, "patient_id": patient_id or ""}
        })
    upsert_vectors(vectors)
    return len(chunks)

@search_bp.route("/search", methods=["POST"])
def run_search():
    query = request.form.get("query", "")
    if not query.strip():
        return render_template("base.html", **base_context(active_tab="search"))
    results = search_notes(query, top_k=5)
    return render_template("base.html", **base_context(search_results=results, search_query=query, active_tab="search"))

@search_bp.route("/ask", methods=["POST"])
def run_ask():
    question = request.form.get("question", "")
    if not question.strip():
        return render_template("base.html", **base_context(active_tab="ask"))

    result = ask_clinical_question(question)
    return render_template("base.html", **base_context(
        ask_question=question,
        ask_answer=result["answer"],
        ask_sources=result.get("sources", []),
        ask_chunks=result.get("chunks", []),
        active_tab="ask"
    ))

@search_bp.route("/ingest", methods=["POST"])
def run_ingest():
    urls_str = request.form.get("urls", "")
    auto_summarize = request.form.get("auto_summarize") == "on"
    urls = [u.strip() for u in urls_str.split("\n") if u.strip()]

    if not urls:
        return render_template("base.html", **base_context(active_tab="ingest"))

    texts = asyncio.run(scrape_multiple_urls(urls))
    ingest_results = []

    for url, text in zip(urls, texts):
        if not text:
            ingest_results.append({"url": url, "success": False, "error": "Could not scrape content"})
            continue

        try:
            patient_id = None
            if auto_summarize:
                try:
                    summary = generate_clinical_summary(text)
                    if not summary.out_of_scope:
                        patient_id = save_patient(summary.model_dump(), text)
                except Exception:
                    pass
            chunks = index_note(url, text, patient_id)
            ingest_results.append({"url": url, "success": True, "chunks": chunks, "patient_id": patient_id})
        except Exception as e:
            ingest_results.append({"url": url, "success": False, "error": str(e)})

    return render_template("base.html", **base_context(ingest_results=ingest_results, active_tab="ingest"))
