# Instruction Clarity Agent

A modular Python agent that processes natural language instructions and either extracts actionable tasks or asks targeted clarification questions. Combines a rule-based pipeline with a Google Gemini LLM fallback for a hybrid AI architecture — no external NLP libraries required for the rule-based layer.

---

## Project Structure

```
agent/
├── __init__.py       # Exposes run()
├── agent.py          # Controller — orchestrates the full pipeline
├── clarity.py        # Clarity analysis and uncertainty detection
├── extractor.py      # Action, deadline, and priority extraction
├── clarifier.py      # Clarification question generation
├── analyzer.py       # Full-instruction clarity analyzer
├── llm.py            # Google Gemini LLM fallback module
└── models.py         # Shared Pydantic models
main.py               # Terminal entry point
requirements.txt      # Dependencies
```

---

## How It Works

### Hybrid Pipeline

```
Raw input
   ↓
1. Noise removal        — strips "hey", "bro", "can you", "please", etc.
   ↓
2. Uncertainty removal  — strips "maybe", "if possible", "possibly", etc.
   ↓
3. Action extraction    — splits into actions, detects deadline + priority
   ↓
4. Action validation    — checks each action for vague pronouns, missing verbs
   ↓
5. Decision
      ├── All actions pronoun-only?  → needs_clarification, actions = []
      ├── Valid actions exist?       → complete, return all actions
      └── No actions at all?        → needs_clarification, actions = []
   ↓
6. Hybrid check
      ├── No actions extracted OR too many clarifications (≥2)?
      │       → call Gemini LLM fallback
      └── Rule-based result is sufficient?
              → return rule-based result
```

### LLM Fallback Trigger

The LLM is called when the rule-based pipeline produces:
- No extracted actions, OR
- 2 or more clarification questions (high ambiguity)

---

## Output Format

Every response is a structured JSON object:

```json
{
  "status": "complete" | "needs_clarification",
  "actions": ["list of extracted action strings"],
  "deadline": "2 days" | "tomorrow" | "next week" | null,
  "priority": "high" | "medium" | "low" | null,
  "clarifications": ["list of targeted questions"]
}
```

---

## Example Inputs and Outputs

### Clear instruction
```
Input:  "fix the login bug and notify the team"

Output:
{
  "status": "complete",
  "actions": ["fix the login bug", "notify the team"],
  "deadline": null,
  "priority": "medium",
  "clarifications": []
}
```

### Instruction with deadline
```
Input:  "finish the report within 2 days"

Output:
{
  "status": "complete",
  "actions": ["finish the report"],
  "deadline": "2 days",
  "priority": "medium",
  "clarifications": []
}
```

### Instruction with noise
```
Input:  "hey bro can you like fix the login issue"

Output:
{
  "status": "complete",
  "actions": ["fix the login issue"],
  "deadline": null,
  "priority": "medium",
  "clarifications": []
}
```

### Instruction with uncertainty
```
Input:  "maybe fix the login bug"

Output:
{
  "status": "complete",
  "actions": ["fix the login bug"],
  "deadline": null,
  "priority": "medium",
  "clarifications": ["Do you want to confirm this task?"]
}
```

### Partially ambiguous — LLM fallback triggered
```
Input:  "fix it somehow"

Output (via Gemini):
{
  "status": "needs_clarification",
  "actions": [],
  "deadline": null,
  "priority": null,
  "clarifications": [
    "What specifically needs to be fixed?",
    "What does 'it' refer to?"
  ]
}
```

### Pronoun-only instruction
```
Input:  "send it"

Output:
{
  "status": "needs_clarification",
  "actions": [],
  "deadline": null,
  "priority": null,
  "clarifications": ["What does 'it' refer to?"]
}
```

---

## Modules

### `agent.py` — Controller
Orchestrates the full hybrid pipeline. Entry point is `run(instruction: str) -> dict`.

Key functions:
- `_clean_noise(text)` — removes conversational filler phrases and words
- `_clean_action(action)` — cleans individual extracted actions
- `_should_use_llm(result)` — decides whether to fall back to LLM
- `run(instruction)` — main pipeline function

### `clarity.py` — Clarity Analysis
Assesses instructions and individual actions for clarity.

Key functions:
- `analyze(text)` — full instruction clarity check
- `analyze_action(action)` — per-action check, returns targeted clarification questions
- `_check_uncertainty(text)` — detects uncertainty markers
- `_remove_uncertainty(text)` — strips uncertainty words from text
- `all_actions_are_pronoun_based(actions)` — detects pronoun-only instructions

### `extractor.py` — Extraction
Extracts actions, deadline, and priority from a cleaned instruction.

Key functions:
- `extract(instruction)` — public interface, returns `{actions, deadline, priority}`
- `_extract_deadline(text)` — detects relative and fixed deadline expressions
- `_infer_priority(text)` — infers `high`, `medium`, or `low` from keywords
- `_split_into_actions(text)` — splits compound instructions into action phrases

### `clarifier.py` — Clarification Generation
Generates human-like clarification questions from missing fields.

Key functions:
- `clarify(missing_fields)` — maps field names to targeted questions
- `generate_clarifications(instruction)` — pattern-based question generation

### `llm.py` — Gemini LLM Fallback
Calls Google Gemini API with retry logic, schema validation, and safe fallback.

Key functions:
- `call_llm(instruction)` — public interface, returns validated structured dict
- `is_valid_schema(data)` — validates all 5 required keys and types
- `_apply_safe_defaults(data)` — coerces partial responses into valid shape
- `_parse_response(raw)` — parses JSON, validates schema, applies defaults
- `_call_once(instruction)` — single Gemini API call
- `run_tests()` — built-in test runner

### `models.py` — Data Models
Pydantic models for structured I/O:
- `ActionExtractionResult` — `{actions, deadline, priority}`
- `ClarificationResult` — `{instruction, questions}`
- `AgentResponse` — top-level response wrapper

---

## LLM Module Details

### Provider
Google Gemini via the `google-genai` SDK (`gemini-2.0-flash` model).

### Reliability Features
| Feature | Detail |
|---|---|
| Retry on JSON failure | Up to 2 retries |
| Schema validation | All 5 keys checked with correct types |
| Safe defaults | Missing/wrong-typed fields auto-corrected |
| Priority normalization | Invalid values default to `"medium"` |
| Empty response guard | Raises `ValueError` if Gemini returns no text |
| API key validation | Raises `ValueError` at startup if key is missing |
| Fallback response | Always returned on unrecoverable failure |

### Fallback Response
```json
{
  "status": "needs_clarification",
  "actions": [],
  "deadline": null,
  "priority": null,
  "clarifications": ["Could you please rephrase the instruction?"]
}
```

---

## Deadline Detection

| Input | Extracted Deadline |
|---|---|
| `within 2 days` | `2 days` |
| `in 3 hours` | `3 hours` |
| `in 1 week` | `1 weeks` |
| `by tomorrow` | `tomorrow` |
| `next week` | `next week` |
| `end of day` | `end of day` |
| `tonight` | `tonight` |

---

## Priority Detection

| Keywords | Priority |
|---|---|
| `urgent`, `asap`, `critical`, `must`, `now` | `high` |
| `eventually`, `later`, `someday`, `optional` | `low` |
| (anything else) | `medium` |

---

## Noise Words Removed

**Phrases:** `can you`, `could you`, `would you`, `will you`, `please`, `plz`

**Words:** `hey`, `hi`, `hello`, `like`, `just`, `so`, `bro`, `dude`, `man`, `mate`, `also`

---

## Installation

```bash
pip install -r requirements.txt
```

**requirements.txt**
```
pydantic>=2.0
google-genai>=1.0
```

---

## Environment Setup

```bash
export GEMINI_API_KEY=your_gemini_api_key_here
```

The agent will raise a `ValueError` at startup if `GEMINI_API_KEY` is not set.

---

## Usage

### Terminal (interactive)
```bash
python3 main.py
```

### Programmatic
```python
from agent.agent import run

result = run("deploy the updated service to production urgently")
print(result)
# {
#   "status": "complete",
#   "actions": ["deploy the updated service to production urgently"],
#   "deadline": null,
#   "priority": "high",
#   "clarifications": []
# }
```

### Test LLM module directly
```bash
python -m agent.llm
```

---

## Design Principles

- **Hybrid architecture** — rule-based pipeline runs first; LLM is a fallback, not the default
- **No external NLP libraries** — rule-based layer uses only Python stdlib + regex
- **Non-destructive validation** — actions are never dropped due to ambiguity; clarifications are generated instead
- **Partial success** — mixed instructions return valid actions alongside clarification questions
- **Stateless** — every call to `run()` is fully independent with no shared state
- **Production-safe LLM** — retry, schema validation, safe defaults, and fallback on every LLM call
