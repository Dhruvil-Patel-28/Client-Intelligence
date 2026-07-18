"""
FastAPI backend for the Client Intelligence Analyzer.

Endpoints:
  POST /analyze  — accepts { "transcript": "..." }, runs the two-stage pipeline
  GET  /sample   — returns the hardcoded sample transcript for one-click loading
"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.graph import graph
from app.sample_transcript import SAMPLE_TRANSCRIPT

app = FastAPI(
    title="Client Intelligence Analyzer",
    description="GenAI-powered client-coach transcript analysis with structural hallucination control",
    version="0.1.0",
)

# ── CORS (wide-open for prototype) ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request model ───────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    transcript: str


# ── POST /analyze ───────────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Run the two-stage LangGraph pipeline:
      1. Extract discrete claims from the transcript
      2. Classify/synthesize into a ClientIntelligenceReport

    Returns the validated report JSON, or a 500 error with details.
    """
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")

    # Run the pipeline
    result = graph.invoke({
        "transcript": req.transcript,
        "claims_json": "",
        "report_json": "",
        "error": "",
    })

    # Check for pipeline errors
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    if not result.get("report_json"):
        raise HTTPException(
            status_code=500,
            detail="Pipeline completed but produced no report.",
        )

    # Return parsed JSON (already validated by Pydantic in the pipeline)
    return json.loads(result["report_json"])


# ── GET /sample ─────────────────────────────────────────────────────────────
@app.get("/sample")
async def get_sample():
    """Return the hardcoded sample transcript for the frontend to pre-load."""
    return {"transcript": SAMPLE_TRANSCRIPT}
