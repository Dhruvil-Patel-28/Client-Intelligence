# Failure Scenarios & Mitigations

This document catalogs the key failure modes of the Client Intelligence Analyzer and the structural, prompt-level, and runtime mitigations in place.

---

## 1. LLM Returns Invalid JSON

**Scenario:** The Anthropic API returns text that is not valid JSON — e.g., markdown-fenced output, trailing commentary, or truncated responses.

**Mitigation:**
- Both pipeline stages strip markdown code fences (```` ``` ````) before parsing.
- Both stages implement a **retry-once** mechanism: if `json.loads()` fails, the parse error is appended to a retry prompt asking for corrected JSON only.
- If the retry also fails, a clear error message is returned to the frontend and displayed in the UI error banner.

---

## 2. Hallucination: Model Invents Data Not in the Transcript

**Scenario:** The model fabricates metrics, quotes, or claims that don't appear in the source transcript.

**Mitigation:**
- **Structural control (primary):** The two-stage LangGraph pipeline enforces that the classification/synthesis node (Stage 2) NEVER sees the raw transcript. It receives only the extracted claims from Stage 1. This means any hallucination at Stage 2 can only draw from already-extracted, quote-backed claims — not from "creative" reinterpretation of the transcript.
- **Prompt-level control (secondary):** Stage 1's system prompt explicitly prohibits summarization, inference, and cross-day data carryforward. Stage 2's system prompt requires every field value to be backed by evidence from the claims.
- **Quote mandate:** Every extracted claim requires a `quote` field with a near-verbatim transcript excerpt, making fabrication auditable.

---

## 3. Cross-Day Data Carryforward

**Scenario:** Day 3 reports "Sleep 5 hours" but Day 4 says nothing about sleep. The model incorrectly assumes Day 4 also had 5 hours of sleep.

**Mitigation:**
- Stage 1 prompt explicitly states: "Do NOT carry forward a value from a previous day unless it is explicitly restated in that day's text."
- Stage 2 enforces `null` for daily_log fields not present in the claims.
- The `"missing"` status taxonomy ensures unfilled fields are flagged as missing, not guessed.

---

## 4. Accountability Coach Claims Merged into Client Data

**Scenario:** An "Accountability Coach" message summarizes the client's data (e.g., "Water 4 litres, Sleep 5 hours"). The model incorrectly tags this as the Client speaking.

**Mitigation:**
- Stage 1 prompt explicitly requires: "Accountability Coach messages that restate/summarize client data must be tagged with speaker 'Accountability Coach', NOT merged into Client claims."
- The speaker field in `ExtractedClaim` supports `"Client"`, `"Coach"`, and `"Accountability Coach"` as distinct values.

---

## 5. Clinical Language in Risk Flags

**Scenario:** The model outputs risk flags using diagnostic terminology like "depression," "burnout," or "anxiety disorder."

**Mitigation:**
- Stage 2 system prompt contains an explicit prohibition: "Explicitly AVOID clinical or diagnostic language (no naming medical/psychological conditions like 'depression,' 'burnout,' 'anxiety disorder' etc.)"
- The prompt instructs framing as pattern observations for coach assessment, not diagnoses.

---

## 6. Status Misclassification

**Scenario:** The model labels an AI inference as a "confirmed_fact" or fills a missing field instead of marking it as "missing."

**Mitigation:**
- The status taxonomy is defined with exact rules in the system prompt, with examples for each category.
- The frontend groups results BY STATUS, making misclassification immediately visible to the reviewer.
- Approve/Edit/Reject buttons allow the coach to override any classification locally.

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
