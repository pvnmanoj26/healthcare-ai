import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from services.clinical_summary import search_notes, ask_clinical_question, chunk_text, generate_clinical_summary
from services.patients import save_patient
from adapters.upstash import upsert_vectors, query_vectors
from adapters.vertex_ai import get_embedding

router = APIRouter(tags=["search"])

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class IngestRequest(BaseModel):
    urls:           List[str]
    auto_summarize: Optional[bool] = False

class IngestResult(BaseModel):
    url:        str
    success:    bool
    chunks:     int           = 0
    patient_id: Optional[str] = None
    error:      Optional[str] = None

class IngestResponse(BaseModel):
    results:      List[IngestResult] = []
    total_chunks: int                = 0

class SearchResult(BaseModel):
    text:       str
    patient_id: Optional[str]   = None
    url:        str              = ""
    score:      Optional[float] = None

class SearchResponse(BaseModel):
    query:   str
    results: List[SearchResult] = []

class AskResponse(BaseModel):
    question: str
    answer:   str
    sources:  List[str] = []

async def scrape_url_async(client, url: str):
    try:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        main = soup.select_one("div.col-lg-9.mainContent")
        if main:
            text = main.get_text(separator=" ").strip()
            text = re.sub(r"\s+", " ", text)
            for stop in ["About This Sample:", "Legal & Usage Notice", "Related Samples"]:
                if stop in text:
                    text = text[:text.index(stop)]
            if len(text.split()) > 50:
                return url, text, None
        return url, None, "No clinical content found"
    except Exception as e:
        return url, None, str(e)

async def scrape_urls_async(urls: list):
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True
    ) as client:
        results = await asyncio.gather(*[scrape_url_async(client, url) for url in urls])
    return results

def index_note(url: str, text: str, patient_id: str = None) -> int:
    chunks = chunk_text(text, chunk_size=512)
    vectors = []
    for i, chunk in enumerate(chunks):
        vectors.append({
            "id":       f"{abs(hash(url))}_{i}",
            "vector":   get_embedding(chunk),
            "data":     chunk,
            "metadata": {"url": url, "chunk": i, "patient_id": patient_id or ""}
        })
    upsert_vectors(vectors)
    return len(chunks)

@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    scraped = asyncio.run(scrape_urls_async(req.urls))
    results = []
    total = 0

    for url, text, error in scraped:
        if not text:
            results.append(IngestResult(url=url, success=False, error=error))
            continue

        chunks_added = index_note(url, text)
        total += chunks_added
        patient_id = None

        if req.auto_summarize:
            try:
                summary = generate_clinical_summary(text)
                if not summary.out_of_scope:
                    patient_id = save_patient(summary.model_dump(), text)
                    flag_count = len(summary.risk_flags)
                    risk_level = "HIGH" if flag_count >= 3 else "MEDIUM" if flag_count >= 1 else "LOW"
                    upsert_vectors([{
                        "id":       f"patient_{patient_id}",
                        "vector":   get_embedding(text[:1000]),
                        "data":     text[:1000],
                        "metadata": {
                            "patient_id":        patient_id,
                            "primary_diagnosis": summary.primary_diagnosis,
                            "risk_level":        risk_level,
                            "url":               url,
                            "chunk":             0
                        }
                    }])
            except Exception as e:
                print(f"Auto-summarize failed: {e}")

        results.append(IngestResult(
            url=url, success=True,
            chunks=chunks_added, patient_id=patient_id
        ))

    return IngestResponse(results=results, total_chunks=total)

@router.post("/search", response_model=SearchResponse)
def search(req: QueryRequest):
    query_vec = get_embedding(req.query)
    results = query_vectors(query_vec, top_k=req.top_k)
    return SearchResponse(
        query=req.query,
        results=[SearchResult(
            text=r.data or "",
            patient_id=r.metadata.get("patient_id"),
            url=r.metadata.get("url", ""),
            score=r.score
        ) for r in results]
    )

@router.post("/ask", response_model=AskResponse)
def ask(req: QueryRequest):
    result = ask_clinical_question(req.query)
    return AskResponse(
        question=req.query,
        answer=result["answer"],
        sources=[s[1] for s in result.get("sources", [])]
    )
