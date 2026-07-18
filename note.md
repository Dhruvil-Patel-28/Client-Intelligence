# Client Intelligence Analyzer — Notes

## Architecture Overview

This prototype demonstrates a **structurally-enforced hallucination control** pattern for GenAI applications, rather than relying solely on prompt engineering.

### Why Two Stages?

The core insight is that LLMs hallucinate most when they have access to rich, unstructured context and are asked to both extract and interpret simultaneously. By splitting extraction and synthesis into two separate LangGraph nodes with a strict data boundary:

1. **Stage 1 (Extraction)** sees the raw transcript and must produce only atomic, quote-backed claims — no interpretation allowed.
2. **Stage 2 (Synthesis)** sees ONLY the extracted claims — never the raw transcript. It cannot "creatively reinterpret" the source because it never sees it.

This is analogous to a compiler's separate lexing and parsing phases: by constraining what each stage can see and produce, we get structural guarantees that no single prompt can provide.

### Status Taxonomy

The four-level status system (`confirmed_fact`, `client_reported`, `ai_inference`, `missing`) forces the model to explicitly label its epistemic confidence for every output field. This means:

- Coaches immediately see what's grounded vs. inferred
- Missing data is flagged rather than silently filled
- AI inferences carry explicit "needs judgment" warnings

### Risk Flag Design

Risk flags deliberately avoid clinical/diagnostic language. The model describes **observed patterns** with citations and flags them for coach attention. This prevents the AI from overstepping into clinical territory while still surfacing important patterns.

## Running the Prototype

```bash
# 1. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API key
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# 4. Start the backend
uvicorn app.main:app --reload

# 5. Open the frontend
# Open frontend/index.html in a browser
```

## Limitations

- **No persistence**: Single-session in-memory only. Card approve/edit/reject states are local JS only.
- **No auth**: Wide-open CORS, no user management.
- **No streaming**: Both LLM calls are blocking; for long transcripts this means a wait.
- **No chunk handling**: Very long transcripts may exceed context limits.
- **No unit tests**: Prototype only — production would need comprehensive test coverage.

## Future Improvements

- Add streaming responses for real-time progress feedback
- Implement transcript chunking for long conversations
- Add a database layer for persisting reports and coach feedback
- Build a coach review workflow with approval state management
- Add export capabilities (PDF, structured JSON)
- Implement token counting and cost estimation before analysis
