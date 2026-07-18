# Failure Scenarios & Mitigations

This document catalogs the key failure modes of the Client Intelligence Analyzer and the structural, prompt-level, and runtime mitigations in place.

---

## 1. LLM Returns Invalid JSON

**Scenario:** The LLM API returns text that is not valid JSON — e.g., markdown-fenced output, trailing commentary, or truncated responses.

**Mitigation:**
- Both pipeline stages strip markdown code fences (```` ``` ````) before parsing.
- Both stages implement a **retry-once** mechanism: if `json.loads()` fails, the parse error is appended to a retry prompt asking for corrected JSON only.
- If the retry also fails, a clear error message is returned to the frontend and displayed in the UI error banner.

---

## 2. API Rate Limit / Model Downgrade Schema Hallucination (Observed)

**Scenario:** During testing, the `llama-3.3-70b-versatile` model hit Groq's Tokens-Per-Day limit. To bypass this, the backend temporarily downgraded to `llama-3.1-8b-instant`. The smaller 8B model repeatedly hallucinated invalid categorical values for Pydantic literals (e.g., generating `client-reported` with a hyphen instead of `client_reported`). This caused validation failures and resulted in the UI generating empty "Day N" data.

**Why this is severe:** A weaker model fails to follow strict taxonomy formatting instructions, breaking down the pipeline entirely rather than just degrading reasoning quality gracefully.

**Mitigation added:** 
- Added a `@field_validator(mode="before")` to `schema.py` to aggressively sanitize and map common hallucinatory variations (like hyphens instead of underscores) back to the strict `Status` taxonomy before Pydantic validation fails.
- Reverted to `llama-3.3-70b-versatile` as the designated production model since extraction and taxonomy enforcement require >8B parameter competence.

---

## 3. Silent Extraction Omission (Observed)

**Scenario:** The Day 7 "Accountability Coach: Tried calling you. Please update when free." line was dropped entirely during extraction on llama-3.3-70b-versatile — zero claims were produced for it, with no error, warning, or downstream signal that anything was missing.

**Why this is severe:** A mislabeled claim is still visible and can be caught by review; an omitted claim leaves no trace anywhere in the pipeline, so neither Stage 2 nor a human reviewer has any way to know information was lost.

**Mitigation added:** A coverage-check warning in `extract_node` comparing transcript line count to extracted claim count per day/speaker, to surface likely omissions for developer review. Note this is a detection aid, not a guarantee — full mitigation would require deterministic extraction validation or multi-pass extraction.

---

## 4. Cross-Day Data Carryforward

**Scenario:** Day 3 reports "Sleep 5 hours" but Day 4 says nothing about sleep. The model incorrectly assumes Day 4 also had 5 hours of sleep.

**Mitigation:**
- Stage 1 prompt explicitly states: "Do NOT carry forward a value from a previous day unless it is explicitly restated in that day's text."
- Stage 2 enforces `null` for daily_log fields not present in the claims.
- The `"missing"` status taxonomy ensures unfilled fields are flagged as missing, not guessed.

**Note:** VERIFIED — tested against Day 2/Day 4 water and sleep fields; confirmed null in both cases, no carryforward from Day 3's Accountability Coach log.

---

## 5. Accountability Coach Claims Merged into Client Data

**Scenario:** An "Accountability Coach" message summarizes the client's data (e.g., "Water 4 litres, Sleep 5 hours"). The model incorrectly tags this as the Client speaking.

**Mitigation:**
- Stage 1 prompt explicitly requires: "Accountability Coach messages that restate/summarize client data must be tagged with speaker 'Accountability Coach', NOT merged into Client claims."
- The speaker field in `ExtractedClaim` supports `"Client"`, `"Coach"`, and `"Accountability Coach"` as distinct values.

---

## 6. Clinical Language in Risk Flags

**Scenario:** The model outputs risk flags using diagnostic terminology like "depression," "burnout," or "anxiety disorder."

**Mitigation:**
- Stage 2 system prompt contains an explicit prohibition: "Explicitly AVOID clinical or diagnostic language (no naming medical/psychological conditions like 'depression,' 'burnout,' 'anxiety disorder' etc.)"
- The prompt instructs framing as pattern observations for coach assessment, not diagnoses.

**Note:** VERIFIED — actual risk flag output used phrases like 'pattern across days 1-7: fatigue, bloating, and low mood — flagged for coach attention' with zero clinical terminology.

---

## 6. Engagement Level Status Misclassification (Observed)

**Scenario:** `engagement_level` was tagged `client_reported` with value "variable, with client reporting ups and downs in energy and mood," citing quotes like "Generally feeling happy today" — but no such conclusion was ever stated by the client themselves.

**Root cause:** The model conflated the evidentiary basis (self-reported mood statements) with the nature of the conclusion (a synthesized pattern judgment), incorrectly treating a derived generalization as if it were a direct quote.

**Fix applied:** Added an explicit rule distinguishing conclusion-type from evidence-type in the classification prompt (CRITICAL DISTINCTION). Re-verified status now returns `ai_inference`.

---

## 7. API Rate Limits or Network Failures

**Scenario:** The Anthropic API returns a rate-limit error (429) or the network connection drops.

**Mitigation:**
- Currently: the error propagates to the FastAPI endpoint, which returns a 500 with the error detail, displayed in the UI.
- **Future improvement:** Add exponential backoff retry logic and more granular error messages distinguishing rate limits from other failures.

---

## 8. Extremely Long Transcripts

**Scenario:** A transcript exceeds the model's context window, causing truncation or errors.

**Mitigation:**
- Currently: no explicit length check. The Anthropic API will return an error if the input exceeds limits.
- **Future improvement:** Add a pre-flight token count check and either warn the user or chunk the transcript into segments processed independently.

---

## 9. Pydantic Validation Failure

**Scenario:** The LLM returns syntactically valid JSON that doesn't match the expected schema (e.g., missing required fields, wrong types).

**Mitigation:**
- Both stages validate the parsed JSON against Pydantic models (`ExtractedClaim` for Stage 1, `ClientIntelligenceReport` for Stage 2).
- Validation errors trigger the retry mechanism with the specific error details included in the retry prompt.

---

## 10. Frontend State Inconsistency

**Scenario:** User approves/edits/rejects cards but the state is lost on page refresh.

**Mitigation:**
- This is a known limitation of the prototype — all card state is held in local JavaScript memory only.
- **Future improvement:** Persist card states to localStorage or add a backend persistence layer.
