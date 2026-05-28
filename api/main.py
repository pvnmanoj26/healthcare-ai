import os
from datetime import datetime, timezone
from fastapi import FastAPI
from api.routes.patients import router as patients_router
from api.routes.summarizer import router as summarizer_router
from api.routes.search import router as search_router

app = FastAPI(title="Clinical AI API", version="1.0.0")

@app.get("/")
def root():
    return {
        "service": "Clinical AI API",
        "version": "1.0.0",
        "docs":    "/docs",
        "endpoints": {
            "health":    "GET  /health",
            "patients":  "GET  /patients",
            "patient":   "GET  /patients/{id}",
            "summarize": "POST /summarize",
            "caregaps":  "POST /caregaps",
            "search":    "POST /search",
            "ask":       "POST /ask",
            "ingest":    "POST /ingest"
        }
    }

@app.get("/health")
def health():
    return {
        "status":    "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Register Routers
app.include_router(patients_router)
app.include_router(summarizer_router)
app.include_router(search_router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
