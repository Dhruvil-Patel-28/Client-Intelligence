"""
FastAPI backend for the Client Intelligence Analyzer.

Endpoints:
  POST /analyze  — accepts { "transcript": "..." }, runs the two-stage pipeline
  GET  /sample   — returns the hardcoded sample transcript for one-click loading
"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
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
def analyze(req: AnalyzeRequest):
    """
    Run the two-stage LangGraph pipeline and stream status updates to the frontend.
    Yields SSE strings dynamically as each stage of the LangGraph completes.
    """
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")

    def event_generator():
        yield f"data: {json.dumps({'status': 'extracting', 'message': 'Reading transcript and extracting claims...'})}\n\n"
        
        try:
            for event in graph.stream(
                {"transcript": req.transcript, "claims_json": "", "report_json": "", "error": ""}
            ):
                if "extract" in event:
                    state_update = event["extract"]
                    if state_update.get("error"):
                        yield f"data: {json.dumps({'status': 'error', 'message': state_update['error']})}\n\n"
                        return
                    yield f"data: {json.dumps({'status': 'classifying', 'message': 'Claims extracted. Synthesizing final report...'})}\n\n"
                
                if "classify" in event:
                    state_update = event["classify"]
                    if state_update.get("error"):
                        yield f"data: {json.dumps({'status': 'error', 'message': state_update['error']})}\n\n"
                        return
                    yield f"data: {json.dumps({'status': 'validating', 'message': 'Draft generated. Automated Judge checking for hallucinations...'})}\n\n"
                
                if "validate" in event:
                    state_update = event["validate"]
                    feedback = state_update.get("validation_feedback")
                    if feedback:
                        yield f"data: {json.dumps({'status': 're-classifying', 'message': f'Judge caught an error: {feedback}. Auto-correcting...'})}\n\n"
                    else:
                        # Validation passed (or max attempts reached)
                        if not state_update.get("report_json"):
                            yield f"data: {json.dumps({'status': 'error', 'message': 'Pipeline completed but produced no report.'})}\n\n"
                            return
                        yield f"data: {json.dumps({'status': 'complete', 'report_json': json.loads(state_update['report_json'])})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'Server error: {str(e)}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── GET /sample ─────────────────────────────────────────────────────────────
@app.get("/sample")
async def get_sample():
    """Return the hardcoded sample transcript for the frontend to pre-load."""
    return {"transcript": SAMPLE_TRANSCRIPT}
