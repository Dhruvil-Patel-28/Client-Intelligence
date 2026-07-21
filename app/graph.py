"""
Two-stage LangGraph pipeline for client intelligence analysis.

STAGE 1 (extract_node): Raw transcript → list of ExtractedClaim objects.
STAGE 2 (classify_node): Claims JSON only → ClientIntelligenceReport.

The architectural separation ensures the classification node never sees the raw
transcript, which structurally prevents ungrounded hallucination at synthesis time.
"""

import json
import os
from typing import TypedDict
from collections import defaultdict

from groq import Groq
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from app.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT,
    EXTRACTION_RETRY_PROMPT,
    CLASSIFICATION_SYSTEM_PROMPT,
    CLASSIFICATION_USER_PROMPT,
    CLASSIFICATION_RETRY_PROMPT,
    VALIDATION_SYSTEM_PROMPT,
    VALIDATION_USER_PROMPT,
)
from app.schema import ExtractedClaim, ClientIntelligenceReport

load_dotenv()

# ── Groq client ─────────────────────────────────────────────────────────────
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


# ── Graph state ─────────────────────────────────────────────────────────────
class PipelineState(TypedDict):
    transcript: str
    claims_json: str          # serialised JSON array of claims
    report_json: str          # serialised final report
    error: str                # to capture fatal pipeline errors
    validation_feedback: str  # feedback from validation node
    validation_attempts: int  # prevent infinite loops


# ── Helpers ─────────────────────────────────────────────────────────────────
def _call_llm(system: str, user: str, max_tokens: int = 8192) -> str:
    """Send a single message to the Groq API and return the text."""
    response = _client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences if the model wraps its output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


# ── STAGE 1: Extraction node ───────────────────────────────────────────────
def _check_extraction_coverage(transcript: str, claims_data: list):
    """
    Simple heuristic coverage check to detect silent extraction omissions.
    Compares transcript lines per day/speaker to extracted claims.
    """
    transcript_counts = defaultdict(lambda: defaultdict(int))
    current_day = "Unknown"
    for line in transcript.split("\n"):
        line = line.strip()
        if line.lower().startswith("day "):
            current_day = line
        else:
            for speaker in ["Client:", "Coach:", "Accountability Coach:"]:
                if line.startswith(speaker):
                    sp = speaker[:-1] # remove colon
                    transcript_counts[current_day][sp] += 1
                    
    claims_counts = defaultdict(lambda: defaultdict(int))
    for c in claims_data:
        claims_counts[c.get("day")][c.get("speaker")] += 1
        
    for day, speakers in transcript_counts.items():
        for speaker, line_count in speakers.items():
            c_count = claims_counts[day][speaker]
            if line_count > 0 and c_count == 0:
                print(f"⚠️ WARNING [Coverage Check]: {day} - {speaker} had {line_count} line(s) in transcript but 0 claims were extracted.")

def extract_node(state: PipelineState) -> dict:
    """
    Extract discrete claims from the raw transcript.
    Returns strict JSON array of claim objects.
    Retries once on JSON parse failure.
    """
    transcript = state["transcript"]
    user_prompt = EXTRACTION_USER_PROMPT.format(transcript=transcript)

    raw = _call_llm(EXTRACTION_SYSTEM_PROMPT, user_prompt)
    raw = _strip_json_fences(raw)

    # First parse attempt
    try:
        claims_data = json.loads(raw)
        # Validate each claim against the schema
        _ = [ExtractedClaim(**c) for c in claims_data]
        _check_extraction_coverage(transcript, claims_data)
        return {"claims_json": json.dumps(claims_data, ensure_ascii=False)}
    except (json.JSONDecodeError, Exception) as first_err:
        first_err_msg = str(first_err)

    # ── Retry once ──────────────────────────────────────────────────────
    retry_prompt = EXTRACTION_RETRY_PROMPT.format(error=first_err_msg)
    raw_retry = _call_llm(EXTRACTION_SYSTEM_PROMPT, retry_prompt)
    raw_retry = _strip_json_fences(raw_retry)

    try:
        claims_data = json.loads(raw_retry)
        _ = [ExtractedClaim(**c) for c in claims_data]
        _check_extraction_coverage(transcript, claims_data)
        return {"claims_json": json.dumps(claims_data, ensure_ascii=False)}
    except (json.JSONDecodeError, Exception) as second_err:
        return {
            "error": (
                f"Extraction failed after retry. "
                f"First error: {first_err_msg}  |  Retry error: {second_err}"
            )
        }


# ── STAGE 2: Classification / synthesis node ───────────────────────────────
def classify_node(state: PipelineState) -> dict:
    """
    Synthesise the intelligence report from extracted claims ONLY.
    Never receives the raw transcript — this is the structural hallucination guard.
    Retries once on JSON parse failure.
    """
    # Short-circuit if extraction already failed
    if state.get("error"):
        return {}

    claims_json = state["claims_json"]
    feedback = state.get("validation_feedback", "")
    
    # If we are retrying due to validation failure, append the judge's feedback
    if feedback:
        user_prompt = CLASSIFICATION_USER_PROMPT.format(claims_json=claims_json) + f"\n\nPREVIOUS ATTEMPT FAILED VALIDATION. JUDGE FEEDBACK:\n{feedback}\nFix the report accordingly."
    else:
        user_prompt = CLASSIFICATION_USER_PROMPT.format(claims_json=claims_json)

    raw = _call_llm(CLASSIFICATION_SYSTEM_PROMPT, user_prompt, max_tokens=8192)
    raw = _strip_json_fences(raw)

    # First parse attempt
    try:
        report_data = json.loads(raw)
        # Validate against Pydantic schema
        _ = ClientIntelligenceReport(**report_data)
        return {"report_json": json.dumps(report_data, ensure_ascii=False)}
    except (json.JSONDecodeError, Exception) as first_err:
        first_err_msg = str(first_err)

    # ── Retry once ──────────────────────────────────────────────────────
    retry_prompt = CLASSIFICATION_RETRY_PROMPT.format(error=first_err_msg)
    raw_retry = _call_llm(CLASSIFICATION_SYSTEM_PROMPT, retry_prompt)
    raw_retry = _strip_json_fences(raw_retry)

    try:
        report_data = json.loads(raw_retry)
        _ = ClientIntelligenceReport(**report_data)
        return {"report_json": json.dumps(report_data, ensure_ascii=False)}
    except (json.JSONDecodeError, Exception) as second_err:
        return {
            "error": (
                f"Classification failed after retry. "
                f"First error: {first_err_msg}  |  Retry error: {second_err}"
            )
        }


# ── Node: Validation (Auto-Correction) ──────────────────────────────────────
def validation_node(state: PipelineState) -> dict:
    """Stage 3: Acts as an automated judge to catch hallucinations or clinical language."""
    # If we already have a hard error from classify, pass it through
    if state.get("error"):
        return {}

    attempts = state.get("validation_attempts", 0) + 1
    if attempts >= 3:
        # Give up after 3 tries to avoid infinite loop
        return {"validation_attempts": attempts, "validation_feedback": "", "report_json": state.get("report_json", "")}

    report_json = state["report_json"]
    user_prompt = VALIDATION_USER_PROMPT.format(report_json=report_json)

    raw = _call_llm(VALIDATION_SYSTEM_PROMPT, user_prompt, max_tokens=500)
    raw = _strip_json_fences(raw)

    try:
        data = json.loads(raw)
        if data.get("is_valid"):
            return {"validation_attempts": attempts, "validation_feedback": "", "report_json": report_json}
        else:
            return {"validation_attempts": attempts, "validation_feedback": data.get("reason", "Unknown validation error"), "report_json": report_json}
    except Exception as e:
        # If the judge fails to return JSON, just let it pass rather than looping infinitely
        return {"validation_attempts": attempts, "validation_feedback": "", "report_json": report_json}


# ── Conditional edge: skip classify if extraction errored ───────────────────
def _should_classify(state: PipelineState) -> str:
    if state.get("error"):
        return END
    return "classify"

def _should_end(state: PipelineState) -> str:
    if state.get("error"):
        return END
    if state.get("validation_feedback"):
        return "classify"
    return END

# ── Build the graph ─────────────────────────────────────────────────────────
def build_graph():
    """Construct and compile the three-stage LangGraph pipeline."""
    builder = StateGraph(PipelineState)

    builder.add_node("extract", extract_node)
    builder.add_node("classify", classify_node)
    builder.add_node("validate", validation_node)

    builder.set_entry_point("extract")
    builder.add_conditional_edges("extract", _should_classify, {"classify": "classify", END: END})
    builder.add_edge("classify", "validate")
    builder.add_conditional_edges("validate", _should_end, {"classify": "classify", END: END})

    return builder.compile()


# Pre-compiled graph instance
graph = build_graph()
