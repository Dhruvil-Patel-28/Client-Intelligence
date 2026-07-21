# Client Intelligence Analyzer

A GenAI product prototype that takes a raw client-coach wellness conversation transcript and produces a **structured, evidence-grounded intelligence report**. Every piece of output is explicitly labeled with its epistemic status (fact, self-report, inference, or missing), and every claim is backed by a verbatim quote.

## 🧠 Core Architecture: Structural Hallucination Control

The core innovation of this project is not prompt engineering — it is **architectural separation**. 

LLMs hallucinate most when given rich, unstructured context and asked to simultaneously extract and interpret. This project uses a three-stage LangGraph pipeline:

1. **Stage 1 (Extraction Node):** Reads the raw transcript and extracts a structured JSON array of atomic, quote-backed claims. It is explicitly forbidden from summarizing or inferring.
2. **Stage 2 (Classification Node):** Synthesizes the final intelligence report. **Crucially, Stage 2 never receives the raw transcript.** It can only build the report using the claims array produced by Stage 1.
3. **Stage 3 (Validation Node):** Acts as an automated judge. It reviews the draft report to ensure no clinical language or hallucinated cross-day carryforwards sneaked in. If it fails, it rejects the draft back to Stage 2 with feedback for an auto-correction rewrite.

This creates a structural guarantee: the synthesis engine cannot "creatively reinterpret" the source text because it simply cannot see it, and the validation node acts as a strict guardrail before the user ever sees the output.

## ✨ Key Features

- **Auto-Correction Agent Loop:** A 3rd LLM node automatically reviews and loops back to fix hallucinations or clinical language before the user sees the output.
- **Interactive Evidence Grounding:** Clicking on any extracted quote in the UI instantly scrolls to and highlights the verbatim sentence in the original transcript.
- **Draft Reply Generation:** Auto-drafts an empathetic WhatsApp/SMS message for the coach based on the intelligence and recommended next actions.
- **Visual Trend Sparklines:** Converts basic text tables into visual CSS progress bars for steps, water, and sleep.
- **Epistemic Status Taxonomy:** Results are grouped by confidence, not just by category.
  - `confirmed_fact`: Objective logged metrics (e.g., from an Accountability Coach).
  - `client_reported`: Client estimates and self-reported symptoms.
  - `ai_inference`: Derived pattern judgments (e.g., "engagement is variable").
  - `missing`: Explicitly missing data; the model is constrained to output `null` rather than guessing.
- **Risk Flagging Constraints:** Identifies concerning patterns (e.g., extreme fatigue) but is strictly prohibited from using clinical/diagnostic language (e.g., "depression").
- **No Cross-Day Carryforward:** Explicitly prevents the model from lazily assuming a metric from Day 3 still applies on Day 4 if unstated.
- **Real-time Streaming UX:** Uses Server-Sent Events (SSE) to push progress updates to the frontend during the multi-stage pipeline, avoiding long loading freezes.
- **Coach Override UI:** The frontend allows coaches to formally ✓ Approve, ✎ Edit, or ✕ Reject any generated card.

## 🛠️ Tech Stack

- **Backend:** Python, FastAPI, LangGraph, Pydantic
- **LLM Provider:** Groq (`llama-3.3-70b-versatile`)
- **Frontend:** Vanilla HTML / CSS / JS (No build step, runs locally)

## 🚀 Quick Start

### 1. Setup the Backend
```bash
# Clone the repo and enter the directory
git clone https://github.com/Dhruvil-Patel-28/Client-Intelligence.git
cd Client_Intelligence

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Add your API Key
echo "GROQ_API_KEY=your-groq-api-key-here" > .env
```

### 2. Run the Server
```bash
uvicorn app.main:app --reload
```
The API will start at `http://localhost:8000`.

### 3. Open the UI
Because the backend serves the frontend directly, simply open your browser and navigate to:
```text
http://localhost:8000
```

Click **"Load Sample Transcript"** to populate the 8-day test conversation, then click **"Analyze Transcript"**.

## 📂 Project Structure

```text
Client_Intelligence/
├── app/
│   ├── schema.py              # Pydantic data contracts (Input/Output validation)
│   ├── prompts.py             # System & User prompt templates
│   ├── graph.py               # The three-stage LangGraph pipeline (extract, classify, validate)
│   ├── main.py                # FastAPI server and endpoints (SSE streaming)
│   └── sample_transcript.py   # Hardcoded 8-day edge-case transcript
├── frontend/
│   └── index.html             # Single-file UI with state management
├── failure_scenarios.md       # Catalog of observed edge cases and mitigations
├── note.md                    # Architecture and design decisions
└── requirements.txt
```

## 🧪 Testing & Edge Cases

This prototype has been validated against a specifically designed 8-day test transcript containing multiple edge cases:
- Missing daily metrics
- Vague estimations ("around 5 hours")
- Mixed speaker provenance (Client vs. Accountability Coach)
- Complex mood/fatigue patterns

For a detailed breakdown of how the architecture mitigates hallucinations, carryforwards, and status misclassifications (along with observed LLaMA-specific quirks), see [`failure_scenarios.md`](failure_scenarios.md).
