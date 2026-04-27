"""Clarification generator — produces targeted questions for unclear instructions."""

import re
from .models import ClarificationResult

# Question templates keyed to detected ambiguity signals
_QUESTION_TEMPLATES: list[tuple[str, str]] = [
    (r"\bfix\b", "What specifically needs to be fixed, and what is the current vs. expected behavior?"),
    (r"\bimprove\b|\bbetter\b", "What aspect should be improved, and what does success look like?"),
    (r"\bupdate\b", "What should be updated, and what should the new state be?"),
    (r"\bsomething\b|\bstuff\b|\bthings?\b", "Can you describe more specifically what you'd like done?"),
    (r"\bmaybe\b|\bperhaps\b", "Are you certain this change is needed? If so, can you clarify the requirement?"),
    (r"\bmake it work\b", "What is the current failure mode, and what does 'working' mean in this context?"),
]

_FALLBACK_QUESTIONS = [
    "What is the goal or desired outcome of this instruction?",
    "Who is the intended audience or user affected by this?",
    "Are there any constraints, deadlines, or dependencies to be aware of?",
]


def generate_clarifications(instruction: str) -> ClarificationResult:
    """
    Generate a list of clarifying questions for an ambiguous instruction.
    """
    lower = instruction.lower()
    questions: list[str] = []
    seen: set[str] = set()

    for pattern, question in _QUESTION_TEMPLATES:
        if re.search(pattern, lower) and question not in seen:
            questions.append(question)
            seen.add(question)

    # Always append fallback questions if we don't have enough
    for q in _FALLBACK_QUESTIONS:
        if len(questions) >= 3:
            break
        if q not in seen:
            questions.append(q)
            seen.add(q)

    return ClarificationResult(instruction=instruction, questions=questions)


# Maps field names (from clarity.py) to human-like clarification questions
_FIELD_QUESTIONS: dict[str, str] = {
    "action_verb": "What would you like to do? Please start with a clear action (e.g. send, create, fix).",
    "subject_or_target": "What or who is this instruction about? Please provide more detail.",
    "specificity": "Could you be more specific? Avoid vague terms like 'it', 'stuff', or 'something'.",
    "no_contradiction": "Are you sure about this request? Please remove uncertain language like 'maybe' or 'I guess'.",
}

_FALLBACK_QUESTION = "Could you rephrase your instruction with more detail so I can act on it?"


def clarify(missing_fields: list[str]) -> dict:
    """
    Generate human-like clarification questions from a list of missing fields.

    Args:
        missing_fields: Field names returned by clarity.analyze() when is_clear is False.

    Returns:
        {"clarifications": list[str]}
    """
    questions = [
        _FIELD_QUESTIONS.get(field, _FALLBACK_QUESTION)
        for field in missing_fields
    ]

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique = []
    for q in questions:
        if q not in seen:
            unique.append(q)
            seen.add(q)

    if not unique:
        unique = [_FALLBACK_QUESTION]

    return {"clarifications": unique}
