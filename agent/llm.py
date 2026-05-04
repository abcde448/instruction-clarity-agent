"""
llm.py — OpenAI-backed LLM module for the instruction clarity agent.

Features:
- Strict JSON-only output enforced via system prompt
- Automatic retry (up to MAX_RETRIES) on JSON parse failure
- Schema validation with safe defaults for missing/wrong-typed keys
- Safe fallback response on all failure paths
- Structured logging via Python's logging module
- Built-in test runner
"""

import json
import logging
import os
from google import genai

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client — reads GEMINI_API_KEY from environment
# ---------------------------------------------------------------------------
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not set")
_client = genai.Client(api_key=api_key)

# gemini-2.0-flash: fast, cost-efficient, and widely supported Gemini model
_MODEL = "gemini-2.0-flash"
_TEMPERATURE = 0.2
_MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """
You are an instruction analysis agent. Your ONLY job is to analyze a user instruction and return a JSON object.

STRICT RULES:
- Return ONLY valid JSON. No explanations, no markdown, no text outside the JSON.
- Do not wrap the JSON in code blocks.
- Always include all five keys: status, actions, deadline, priority, clarifications.

OUTPUT FORMAT:
{
  "status": "complete" | "needs_clarification",
  "actions": ["list of clear action strings"],
  "deadline": "time expression or null",
  "priority": "high" | "medium" | "low" | null,
  "clarifications": ["list of clarification questions or empty list"]
}

DECISION RULES:
- If the instruction is clear and actionable:
    status = "complete", actions = extracted phrases, clarifications = []
- If the instruction is vague or ambiguous:
    status = "needs_clarification", clarifications = specific questions

- deadline: extract time expressions like "tomorrow", "next week", "in 2 days", or null
- priority: urgent/asap/critical = high | eventually/later = low | else = medium

EXAMPLES:

Input: "fix the login bug by tomorrow"
Output: {"status":"complete","actions":["fix the login bug"],"deadline":"tomorrow","priority":"medium","clarifications":[]}

Input: "maybe fix it somehow"
Output: {"status":"needs_clarification","actions":[],"deadline":null,"priority":null,"clarifications":["What specifically needs to be fixed?","What does 'it' refer to?"]}

Input: "prepare report and send it to the client within 2 days"
Output: {"status":"complete","actions":["prepare report","send it to the client"],"deadline":"2 days","priority":"medium","clarifications":["What does 'it' refer to?"]}
""".strip()

# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------
_FALLBACK_RESPONSE: dict = {
    "status": "needs_clarification",
    "actions": [],
    "deadline": None,
    "priority": None,
    "clarifications": ["Could you please rephrase the instruction?"],
}

# Valid values for the status field
_VALID_STATUSES = {"complete", "needs_clarification"}
_VALID_PRIORITIES = {"high", "medium", "low", None}


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------
def is_valid_schema(data: dict) -> bool:
    """
    Validate that a parsed LLM response contains all required keys
    with correct types.

    Rules:
    - status: str, must be "complete" or "needs_clarification"
    - actions: list
    - clarifications: list
    - deadline: str or None
    - priority: str or None

    Returns:
        True if schema is valid, False otherwise.
    """
    if not isinstance(data, dict):
        return False

    required_keys = {"status", "actions", "deadline", "priority", "clarifications"}
    if not required_keys.issubset(data.keys()):
        logger.warning("Schema missing keys: %s", required_keys - data.keys())
        return False

    if data["status"] not in _VALID_STATUSES:
        logger.warning("Invalid status value: %s", data["status"])
        return False

    if not isinstance(data["actions"], list):
        logger.warning("'actions' is not a list: %s", type(data["actions"]))
        return False

    if not isinstance(data["clarifications"], list):
        logger.warning("'clarifications' is not a list: %s", type(data["clarifications"]))
        return False

    if data["deadline"] is not None and not isinstance(data["deadline"], str):
        logger.warning("'deadline' must be str or None, got: %s", type(data["deadline"]))
        return False

    if data["priority"] is not None and not isinstance(data["priority"], str):
        logger.warning("'priority' must be str or None, got: %s", type(data["priority"]))
        return False

    return True


def _apply_safe_defaults(data: dict) -> dict:
    """
    Coerce a partially valid dict into a fully valid response
    by filling missing or wrong-typed fields with safe defaults.
    """
    priority = data.get("priority")
    if priority not in _VALID_PRIORITIES:
        priority = "medium"

    return {
        "status": data.get("status") if data.get("status") in _VALID_STATUSES else "needs_clarification",
        "actions": data.get("actions") if isinstance(data.get("actions"), list) else [],
        "deadline": data.get("deadline") if isinstance(data.get("deadline"), (str, type(None))) else None,
        "priority": priority,
        "clarifications": data.get("clarifications") if isinstance(data.get("clarifications"), list) else [],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_response(raw: str) -> dict:
    """
    Parse the raw LLM string, validate schema, and apply safe defaults.

    Raises json.JSONDecodeError if the output is not valid JSON.
    Returns a schema-safe dict in all other cases.
    """
    parsed = json.loads(raw)  # raises JSONDecodeError if not valid JSON

    if not isinstance(parsed, dict):
        logger.warning("LLM returned non-dict JSON: %s", type(parsed))
        return _FALLBACK_RESPONSE

    # Apply safe defaults for any missing or wrong-typed fields
    result = _apply_safe_defaults(parsed)

    if not is_valid_schema(result):
        logger.warning("Schema invalid after applying defaults — using fallback")
        return _FALLBACK_RESPONSE

    return result


def _call_once(instruction: str) -> str:
    """Make a single Gemini API call and return the raw response string."""
    prompt = f"{_SYSTEM_PROMPT}\n\nInstruction: {instruction.strip()}"
    response = _client.models.generate_content(
        model=_MODEL,
        contents=prompt,
    )
    text = getattr(response, "text", None)
    if not text:
        raise ValueError("Empty response from Gemini")
    return text.strip()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
def call_llm(instruction: str) -> dict:
    """
    Send an instruction to the OpenAI API and return a validated response.

    Retries up to MAX_RETRIES times on JSON parse failure.
    Validates schema after parsing and applies safe defaults.
    Returns a safe fallback on all failure paths.

    Args:
        instruction: Raw user instruction string.

    Returns:
        {
            "status":         "complete" | "needs_clarification",
            "actions":        list[str],
            "deadline":       str | None,
            "priority":       str | None,
            "clarifications": list[str]
        }
    """
    if not instruction or not instruction.strip():
        logger.warning("call_llm received empty instruction")
        return {**_FALLBACK_RESPONSE, "clarifications": ["Please provide an instruction."]}

    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info("LLM call attempt %d/%d", attempt, _MAX_RETRIES)
            raw = _call_once(instruction)
            logger.debug("LLM raw output: %s", raw)
            print(f"LLM RAW (attempt {attempt}):", raw)

            result = _parse_response(raw)
            logger.info("LLM response parsed successfully on attempt %d", attempt)
            return result

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning("JSON parse failed on attempt %d: %s", attempt, e)
            print(f"LLM JSON ERROR (attempt {attempt}):", e)

        except Exception as e:
            last_error = e
            logger.error("LLM call failed on attempt %d: %s", attempt, e)
            print(f"LLM ERROR (attempt {attempt}):", e)
            # Non-parse errors (network, auth, rate limit) — no point retrying
            break

    logger.error("All LLM attempts failed. Last error: %s", last_error)
    print("LLM FALLBACK: returning safe response")
    return _FALLBACK_RESPONSE


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
def run_tests() -> None:
    """
    Simple test runner to verify call_llm() against known inputs.
    Run directly: python -m agent.llm
    """
    import json as _json

    test_cases = [
        "send it",
        "fix",
        "hey bro maybe fix it asap",
        "",
        "prepare report and send it to client",
    ]

    print("\n" + "=" * 60)
    print("LLM MODULE TEST RUNNER")
    print("=" * 60)

    for instruction in test_cases:
        label = repr(instruction) if instruction else "(empty string)"
        print(f"\nINPUT: {label}")
        result = call_llm(instruction)
        print("OUTPUT:", _json.dumps(result, indent=2))
        print("-" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_tests()
