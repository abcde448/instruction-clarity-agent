# Instruction Clarity Agent

A modular, rule-based Python agent that processes natural language instructions and either extracts actionable tasks or asks targeted clarification questions — all without any external NLP libraries.

---

## Project Structure

```
agent/
├── __init__.py       # Exposes run()
├── agent.py          # Controller — orchestrates the full pipeline
├── clarity.py        # Clarity analysis and uncertainty detection
├── extractor.py      # Action, deadline, and priority extraction
├── clarifier.py      # Clarification question generation
├── analyzer.py       # (Legacy) Full-instruction clarity analyzer
└── models.py         # Shared Pydantic models
main.py               # Terminal entry point
requirements.txt      # Dependencies
```

---

## How It Works

Every instruction goes through this pipeline:

```
Raw input
   ↓
1. Noise removal       — strips "hey", "bro", "can you", "please", etc.
   ↓
2. Uncertainty removal — strips "maybe", "if possible", "possibly", etc.
   ↓
3. Action extraction   — splits into individual actions, detects deadline + priority
   ↓
4. Action validation   — checks each action for vague pronouns, missing verbs, etc.
   ↓
5. Decision
      ├── All actions pronoun-only?  → needs_clarification, actions = []
      ├── Valid actions exist?       → complete, return all actions
      └── No actions at all?        → needs_clarification, actions = []
   ↓
6. Clarifications built separately — never block valid actions
```

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

### Partially ambiguous instruction
```
Input:  "prepare report and send it to the client"

Output:
{
  "status": "complete",
  "actions": ["prepare report", "send it to the client"],
  "deadline": null,
  "priority": "medium",
  "clarifications": ["What does 'it' refer to?"]
}
```

### Fully unclear instruction
```
Input:  "fix it somehow"

Output:
{
  "status": "needs_clarification",
  "actions": [],
  "deadline": null,
  "priority": null,
  "clarifications": [
    "What does 'it' refer to?",
    "How exactly should 'fix it somehow' be done?"
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
Orchestrates the full pipeline. Entry point is `run(instruction: str) -> dict`.

Key functions:
- `_clean_noise(text)` — removes conversational filler phrases and words
- `_clean_action(action)` — cleans individual extracted actions
- `run(instruction)` — main pipeline function

### `clarity.py` — Clarity Analysis
Assesses instructions and individual actions for clarity.

Key functions:
- `analyze(text)` — full instruction clarity check, returns `{is_clear, missing_fields}`
- `analyze_action(action)` — per-action check, returns targeted clarification questions
- `_check_uncertainty(text)` — detects uncertainty markers, returns `(bool, [questions])`
- `_remove_uncertainty(text)` — strips uncertainty words from text
- `all_actions_are_pronoun_based(actions)` — returns True if every action has only pronouns as its object

### `extractor.py` — Extraction
Extracts actions, deadline, and priority from a cleaned instruction.

Key functions:
- `extract(instruction)` — public interface, returns `{actions, deadline, priority}`
- `_extract_deadline(text)` — detects relative (`within 2 days`, `in 3 hours`) and fixed (`tomorrow`, `next week`) deadlines
- `_infer_priority(text)` — infers `high`, `medium`, or `low` from keywords
- `_split_into_actions(text)` — splits compound instructions into individual action phrases

### `clarifier.py` — Clarification Generation
Generates human-like clarification questions from missing fields.

Key functions:
- `clarify(missing_fields)` — maps field names to targeted questions, returns `{clarifications}`
- `generate_clarifications(instruction)` — pattern-based question generation for full instructions

### `models.py` — Data Models
Pydantic models for structured I/O:
- `ActionExtractionResult` — `{actions, deadline, priority}`
- `ClarificationResult` — `{instruction, questions}`
- `AgentResponse` — top-level response wrapper

---

## Deadline Detection

Supports both relative and fixed time expressions:

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
```

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

---

## Design Principles

- **No external NLP libraries** — fully rule-based, no spaCy, NLTK, or transformers
- **Modular** — each concern is isolated in its own file
- **Non-destructive validation** — actions are never dropped due to ambiguity; clarifications are generated instead
- **Partial success** — mixed instructions (some clear, some vague) return valid actions alongside clarification questions
- **Stateless** — every call to `run()` is fully independent with no shared state
