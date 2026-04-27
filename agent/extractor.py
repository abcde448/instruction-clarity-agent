"""Action extractor — pulls structured action items from a clear instruction."""

import re
from typing import Optional
from .models import ActionExtractionResult

# Ordered by specificity (longer phrases first to avoid partial matches)
_DEADLINE_PATTERNS: list[str] = [
    "next month",
    "next week",
    "next monday",
    "next tuesday",
    "next wednesday",
    "next thursday",
    "next friday",
    "end of day",
    "end of week",
    "end of month",
    "tomorrow",
    "today",
    "tonight",
]

# Prepositions that typically precede a deadline expression
_DEADLINE_PREFIX = r"(?:by|before|due|on|until|no later than)\s+"


def _extract_deadline(text: str) -> tuple[Optional[str], str]:
    """
    Detect and remove a deadline expression from text.

    Supports:
    - Relative time: "within 2 days", "in 3 hours", "in 1 week"
    - Fixed phrases: "tomorrow", "next week", "tonight", etc.

    Returns (deadline_string | None, cleaned_text).
    """
    lower = text.lower()

    # --- Check relative time expressions first ---
    # Matches: (within|in) + number + (hours|days|weeks|months)
    relative_pattern = r"(?:within|in)\s+(\d+)\s+(hour|hours|day|days|week|weeks|month|months)"
    rel_match = re.search(relative_pattern, lower)
    if rel_match:
        quantity = rel_match.group(1)
        unit = rel_match.group(2)
        # Normalise unit to plural
        if not unit.endswith("s"):
            unit += "s"
        deadline = f"{quantity} {unit}"
        before = text[:rel_match.start()].rstrip(" ,-")
        after = text[rel_match.end():].lstrip(" ,-")
        cleaned = (before + (" " if before and after else "") + after).strip().rstrip(".")
        return deadline, cleaned

    # --- Fall back to fixed phrase matching ---
    for phrase in _DEADLINE_PATTERNS:
        pattern = rf"({_DEADLINE_PREFIX})?({re.escape(phrase)})\b"
        match = re.search(pattern, lower)
        if match:
            deadline = phrase
            before = text[:match.start()].rstrip(" ,-")
            after = text[match.end():].lstrip(" ,-")
            cleaned = (before + (" " if before and after else "") + after).strip().rstrip(".")
            return deadline, cleaned

    return None, text

# Keywords that map to priority levels
_HIGH_PRIORITY_KEYWORDS = {"immediately", "urgent", "asap", "critical", "now", "must"}
_LOW_PRIORITY_KEYWORDS = {"eventually", "later", "someday", "optional", "if possible", "when you can"}


def _infer_priority(text: str) -> str:
    lower = text.lower()
    if any(kw in lower for kw in _HIGH_PRIORITY_KEYWORDS):
        return "high"
    if any(kw in lower for kw in _LOW_PRIORITY_KEYWORDS):
        return "low"
    return "medium"


def _split_into_actions(instruction: str) -> list[str]:
    """
    Split a compound instruction into individual action phrases.
    Handles conjunctions, numbered lists, and bullet-style separators.
    """
    # Normalize bullets and numbering
    text = re.sub(r"(\d+[\.\)]\s+)", "\n", instruction)
    text = re.sub(r"([•\-\*]\s+)", "\n", text)

    # Split on conjunctions and punctuation that imply separate tasks
    parts = re.split(r"\band\b|\bthen\b|\balso\b|\bfinally\b|\bfirst\b|\bnext\b|[;,\n]", text, flags=re.IGNORECASE)

    actions = [p.strip().rstrip(".") for p in parts if len(p.strip()) > 5]
    return actions or [instruction.strip()]


def extract_actions(instruction: str) -> ActionExtractionResult:
    """
    Extract actions, shared deadline, and shared priority from an instruction.

    Deadline and priority are resolved from the full instruction so they apply
    to all actions uniformly.
    """
    shared_deadline, cleaned_instruction = _extract_deadline(instruction)
    shared_priority = _infer_priority(instruction)
    raw_actions = _split_into_actions(cleaned_instruction)

    return ActionExtractionResult(
        actions=raw_actions,
        deadline=shared_deadline,
        priority=shared_priority,
    )


def extract(instruction: str) -> dict:
    """
    Public interface — returns a plain dict with actions, deadline, and priority.

    Args:
        instruction: A clear instruction string.

    Returns:
        {
            "actions":  list[str],
            "deadline": str | None,
            "priority": str        # "high" | "medium" | "low"
        }
    """
    result = extract_actions(instruction)
    return {
        "actions": result.actions,
        "deadline": result.deadline,
        "priority": result.priority,
    }
