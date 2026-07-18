"""
Pydantic models for the Client Intelligence Analyzer.

Defines the data contracts for extraction claims, status-tagged fields,
daily logs, and the final intelligence report.
"""

from typing import Literal, Optional
from pydantic import BaseModel


# ── Status taxonomy ──────────────────────────────────────────────────────────
Status = Literal["confirmed_fact", "client_reported", "ai_inference", "missing"]


# ── Stage 1: Extraction output ──────────────────────────────────────────────
class ExtractedClaim(BaseModel):
    day: str
    speaker: str
    claim: str
    category: str
    quote: str


# ── Stage 2: Synthesis building blocks ──────────────────────────────────────
from pydantic import BaseModel, field_validator

class Field(BaseModel):
    value: Optional[str] = None
    status: Status
    evidence: list[str] = []
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("status", mode="before")
    @classmethod
    def sanitize_status(cls, v: str) -> str:
        if isinstance(v, str):
            return v.replace("-", "_")
        return v


class DailyLog(BaseModel):
    day: str
    steps: Optional[str] = None
    water: Optional[str] = None
    sleep_hours: Optional[str] = None
    exercise: Optional[str] = None


# ── Final report ────────────────────────────────────────────────────────────
class ClientIntelligenceReport(BaseModel):
    client_id: str
    period_covered: str
    weekly_summary: str
    daily_logs: list[DailyLog]
    fields: dict[str, Field]
    key_barriers: list[Field]
    pending_actions: list[Field]
    risk_flags: list[Field]
    recommended_next_action: Field
