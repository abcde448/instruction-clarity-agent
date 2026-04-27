"""Clarity analyzer — determines if an instruction is actionable or ambiguous."""

import re
from .models import ClarityResult, ClarityStatus

# Signals that suggest an instruction is vague or incomplete
_VAGUE_PATTERNS = [
    r"\bsomething\b",
    r"\bstuff\b",
    r"\bthings?\b",
    r"\bsomehow\b",
    r"\bmaybe\b",
    r"\bperhaps\b",
    r"\bi (don'?t know|dunno|guess)\b",
    r"\bnot sure\b",
    r"\bfix it\b",
    r"\bmake it (better|good|work)\b",
    r"\bdo (something|stuff)\b",
]

_MIN_WORD_COUNT = 4


def analyze_clarity(instruction: str) -> ClarityResult:
    """
    Analyze whether an instruction is clear enough to act on.

    Returns a ClarityResult with status, confidence, and reasoning.
    """
    text = instruction.strip().lower()
    words = text.split()

    issues: list[str] = []

    if len(words) < _MIN_WORD_COUNT:
        issues.append("instruction is too short to be actionable")

    for pattern in _VAGUE_PATTERNS:
        if re.search(pattern, text):
            issues.append(f"contains vague language matching '{pattern}'")

    if not re.search(r"[a-zA-Z]{3,}", instruction):
        issues.append("no meaningful words detected")

    if issues:
        confidence = max(0.1, 0.5 - 0.1 * len(issues))
        return ClarityResult(
            status=ClarityStatus.UNCLEAR,
            confidence=round(confidence, 2),
            reason="; ".join(issues),
        )

    return ClarityResult(
        status=ClarityStatus.CLEAR,
        confidence=0.9,
        reason="instruction contains sufficient detail to extract actions",
    )
