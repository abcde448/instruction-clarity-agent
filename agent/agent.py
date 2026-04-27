"""
agent.py — Controller that orchestrates clarity, extraction, and clarification.

Output shape:
    {
        "status":         "complete" | "needs_clarification",
        "actions":        list[str],
        "deadline":       str | None,
        "priority":       str | None,
        "clarifications": list[str]
    }
"""

import re
from .clarity import analyze, analyze_action, _check_uncertainty, _remove_uncertainty, all_actions_are_pronoun_based
from .extractor import extract
from .clarifier import clarify


# Common conversational fillers and polite phrases to remove
_NOISE_PHRASES = [
    "can you",
    "could you",
    "would you",
    "will you",
    "please",
    "plz",
]

_NOISE_WORDS = {
    "hey",
    "hi",
    "hello",
    "like",
    "just",
    "so",
    "bro",
    "dude",
    "man",
    "mate",
    "also",  # Only remove when used as filler
}


def _clean_noise(text: str) -> str:
    """
    Remove conversational noise and filler phrases from an instruction.

    Steps:
    1. Lowercase input
    2. Remove phrases using string replace
    3. Then split words and remove remaining noise words
    4. Rejoin clean text
    """
    if not text or not text.strip():
        return text

    print("ORIGINAL:", text)

    # Lowercase for consistent matching
    lower = text.lower()

    # Remove phrases FIRST (before word tokenization)
    for phrase in _NOISE_PHRASES:
        lower = lower.replace(phrase, " ")

    # Tokenize: split into words
    words = lower.split()

    # Filter out noise words
    filtered = [w for w in words if w not in _NOISE_WORDS]

    # Join back cleanly
    cleaned = " ".join(filtered).strip()

    print("CLEANED:", cleaned)
    return cleaned


def _clean_action(action: str) -> str:
    """
    Clean a single extracted action to remove any remaining noise.

    Ensures actions don't contain polite phrases like "can you", "please", etc.
    """
    if not action or not action.strip():
        return action

    lower = action.lower()

    # Remove phrases
    for phrase in _NOISE_PHRASES:
        lower = lower.replace(phrase, " ")

    # Tokenize and filter
    words = lower.split()
    filtered = [w for w in words if w not in _NOISE_WORDS]

    cleaned = " ".join(filtered).strip()
    return cleaned


def run(instruction: str) -> dict:
    """
    Process a user instruction and return a structured response.

    - Cleans conversational noise from input
    - Extracts actions from cleaned input
    - Returns valid actions + clarifications for unclear parts
    - Fully clear instructions get status="complete"
    - Partially clear or uncertain instructions get status="needs_clarification"

    Args:
        instruction: Raw instruction string from the user.

    Returns:
        Structured dict with status, actions, and clarifications.
    """
    if not instruction or not instruction.strip():
        return {
            "status": "needs_clarification",
            "actions": [],
            "deadline": None,
            "priority": None,
            "clarifications": ["Please provide an instruction for me to act on."],
        }

    # Clean conversational noise before processing
    cleaned_instruction = _clean_noise(instruction)
    print("CLEANED:", cleaned_instruction)

    # Check for uncertainty markers
    has_uncertainty, uncertainty_clarifications = _check_uncertainty(cleaned_instruction)

    # Remove uncertainty words from the instruction before extraction
    cleaned_no_uncertainty = _remove_uncertainty(cleaned_instruction)
    print("CLEANED (no uncertainty):", cleaned_no_uncertainty)

    # Always extract actions first (on cleaned input)
    extraction = extract(cleaned_no_uncertainty)
    raw_actions = extraction["actions"]
    print("EXTRACTED:", raw_actions)

    # Clean each extracted action to remove any remaining noise
    cleaned_actions = [_clean_action(a) for a in raw_actions]
    print("ACTIONS (cleaned):", cleaned_actions)

    # Validate each action — collect clarifications but KEEP all actions
    all_clarifications: list[str] = list(uncertainty_clarifications)

    for action in cleaned_actions:
        action_clarity = analyze_action(action)
        # Always keep the action regardless of clarity
        # Only use validation result to generate targeted clarifications
        all_clarifications.extend(action_clarity.get("clarifications", []))

    # final_actions = ALL extracted actions, no filtering
    final_actions = cleaned_actions

    print("FINAL ACTIONS:", final_actions)

    # Decision: if ALL actions are pronoun-only → needs_clarification
    if all_actions_are_pronoun_based(final_actions):
        status = "needs_clarification"
        final_actions = []  # Drop pronoun-only actions
    elif final_actions:
        status = "complete"
    else:
        status = "needs_clarification"

    print("STATUS:", status)

    return {
        "status": status,
        "actions": final_actions,
        "deadline": extraction["deadline"],
        "priority": extraction["priority"],
        "clarifications": list(dict.fromkeys(all_clarifications)),  # deduplicate
    }
