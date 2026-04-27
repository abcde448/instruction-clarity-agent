"""
clarity.py — LLM-style reasoning (rule-based mock) to assess instruction clarity.

Returns a plain dict:
    {"is_clear": bool, "missing_fields": list[str]}

Functions:
- analyze(text): Assess full instruction clarity
- analyze_action(action): Assess individual action phrase clarity
"""

import re

# --- Heuristic rules that simulate LLM reasoning steps ---

# Common nouns that can serve as clear objects (simple heuristic)
_COMMON_NOUNS = {
    "report", "presentation", "email", "message", "file", "document", "task",
    "project", "code", "test", "build", "deployment", "server", "config",
    "data", "user", "account", "bug", "feature", "branch", "commit",
    "meeting", "call",
}

# Generic/vague objects that lack specificity
_VAGUE_OBJECTS = {"issue", "thing", "stuff", "something", "it"}

# Vague modifiers that indicate unclear urgency
_VAGUE_MODIFIERS = {"quickly", "soon", "later", "fast", "immediately"}

# Each entry is (field_name, check_fn, failure_message)
# check_fn receives the lowercased instruction and returns True if the field IS present
_REASONING_CHECKS: list[tuple[str, object, str]] = [
    (
        "action_verb",
        lambda t: bool(re.search(r"\b(send|create|write|fix|update|build|deploy|review|add|remove|delete|generate|prepare|submit|schedule|call|email|test|check|run|set up|configure)\b", t)),
        "no clear action verb found",
    ),
    (
        "subject_or_target",
        lambda t: len(t.split()) >= 4,
        "instruction too short to identify a subject or target",
    ),
    (
        "target",
        lambda t: _check_target(t),
        "generic or vague object detected (e.g. 'issue', 'thing', 'stuff')",
    ),
    (
        "urgency",
        lambda t: _check_urgency(t),
        "vague modifier without clear deadline (e.g. 'quickly', 'soon', 'later')",
    ),
    (
        "specificity",
        lambda t: _check_specificity(t),
        "vague references detected (e.g. 'it', 'stuff', 'something')",
    ),
]


def _check_target(text: str) -> bool:
    """
    Check if the instruction has a specific target, not a generic one.

    Returns True if target is specific, False if it's vague (e.g. "issue", "thing").
    """
    # Check for vague objects
    if re.search(r"\b(issue|thing|stuff|something)\b", text):
        return False
    return True


def _check_urgency(text: str) -> bool:
    """
    Check if urgency is specified clearly.

    Returns True if:
    - No vague modifier (quickly, soon, later) is present, OR
    - A vague modifier is present but a clear deadline follows

    Returns False if a vague modifier appears without a clear deadline.
    """
    # Check for vague modifiers
    has_vague_modifier = bool(re.search(r"\b(quickly|soon|later|fast|immediately)\b", text))

    if not has_vague_modifier:
        return True  # No urgency issue

    # If there's a vague modifier, check for a clear deadline after it
    # Look for deadline patterns that appear after the modifier
    deadline_patterns = [
        r"\b(by\s+(tomorrow|today|next\s+(week|month)|end\s+of\s+(day|week|month)))",
        r"\b(due\s+on)",
    ]

    for pattern in deadline_patterns:
        if re.search(pattern, text):
            return True  # Deadline follows, so urgency is clarified

    return False  # Vague modifier without deadline


def _check_specificity(text: str) -> bool:
    """
    Check if the instruction avoids vague references.

    Special handling for pronouns like "it" — if there's a clear noun before
    the pronoun, it's considered contextually defined and acceptable.
    """
    # Check for truly vague standalone words
    if re.search(r"\b(something|stuff|things?|somehow)\b", text):
        return False

    # Check for "it" / "this" / "that" — allow if preceded by a clear noun
    # Pattern: [noun] followed by [it|this|that]
    pronoun_pattern = r"\b(it|this|that)\b"
    if not re.search(pronoun_pattern, text):
        return True  # No pronouns to check

    # Extract words before the pronoun
    pronoun_match = re.search(pronoun_pattern, text)
    if not pronoun_match:
        return True

    before_pronoun = text[: pronoun_match.start()].strip()
    words_before = before_pronoun.split()

    # If we have at least 2 words before the pronoun, look for a noun
    if len(words_before) >= 2:
        # Check if the last word before the pronoun is a known noun
        last_word = words_before[-1].rstrip(".,;:")
        if last_word in _COMMON_NOUNS:
            return True  # Context is defined

    # Fallback: if the instruction is long enough, assume context is implied
    if len(text.split()) >= 5:
        return True

    return False


def _reasoning_steps(text: str) -> list[str]:
    """
    Simulate LLM chain-of-thought by running each heuristic check
    and collecting the names of fields that fail.
    """
    lower = text.lower().strip()
    missing: list[str] = []

    for field, check, _ in _REASONING_CHECKS:
        if not check(lower):
            missing.append(field)

    return missing


def analyze(text: str) -> dict:
    """
    Assess whether a text instruction is clear enough to act on.

    Args:
        text: Raw instruction string from the user.

    Returns:
        {
            "is_clear": bool,
            "missing_fields": list[str]   # empty when is_clear is True
        }
    """
    if not text or not text.strip():
        return {
            "is_clear": False,
            "missing_fields": ["action_verb", "subject_or_target", "specificity"],
        }

    missing_fields = _reasoning_steps(text)

    return {
        "is_clear": len(missing_fields) == 0,
        "missing_fields": missing_fields,
    }


# Uncertainty markers and their corresponding clarification prompts
_UNCERTAINTY_MARKERS = [
    (r"\b(maybe|perhaps)\b", "Do you want to confirm this task?"),
    (r"\bi guess\b", "What is your confidence level in this instruction?"),
    (r"\bnot sure\b", "What would you like me to do if you're not sure?"),
    (r"\bi don'?t know\b|\bdunno\b", "What information would help clarify this request?"),
    (r"\bif possible\b", "Is this action optional, or should I proceed when feasible?"),
    (r"\bpossibly\b", "Should I proceed with this task?"),
]


def _check_uncertainty(text: str) -> tuple[bool, list[str]]:
    """
    Detect uncertainty markers in the instruction.

    Returns:
        (has_uncertainty: bool, clarifications: list[str])
    """
    lower = text.lower()
    clarifications = []

    for pattern, msg in _UNCERTAINTY_MARKERS:
        if re.search(pattern, lower):
            clarifications.append(msg)

    return (len(clarifications) > 0, clarifications)


def _remove_uncertainty(text: str) -> str:
    """
    Remove uncertainty markers from text.

    Returns cleaned text with uncertainty words removed.
    """
    if not text:
        return text

    cleaned = text
    for pattern, _ in _UNCERTAINTY_MARKERS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Clean up extra whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def all_actions_are_pronoun_based(actions: list[str]) -> bool:
    """
    Returns True if every action depends solely on a vague pronoun
    with no concrete noun as the object.

    e.g. ["fix it", "send it"] → True
         ["prepare report", "send it"] → False
    """
    if not actions:
        return False

    for action in actions:
        lower = action.lower()
        words = lower.split()

        # Remove the verb (first word) to inspect the object
        object_words = words[1:] if len(words) > 1 else words

        # If any non-pronoun, non-preposition word exists → action has a real object
        _PRONOUNS = {"it", "this", "that", "them", "they", "those", "these"}
        _PREPOSITIONS = {"to", "for", "at", "on", "in", "by", "with", "from", "of", "the", "a", "an"}

        meaningful = [
            w for w in object_words
            if w not in _PRONOUNS and w not in _PREPOSITIONS
        ]

        if meaningful:
            return False  # This action has a real object → not pronoun-only

    return True  # All actions are pronoun-only


def analyze_action(action: str) -> dict:
    """
    Assess a single action phrase and return targeted clarifications.

    Does NOT filter out the action — only generates clarification prompts
    for ambiguous parts so the caller can keep the action and ask questions.
    """
    if not action or not action.strip():
        return {"is_clear": False, "clarifications": ["Please provide a valid action."]}

    lower = action.lower()
    clarifications: list[str] = []

    # Check for a clear action verb
    has_verb = bool(re.search(
        r"\b(send|create|write|fix|update|build|deploy|review|add|remove|delete|"
        r"generate|prepare|submit|schedule|call|email|test|check|run|set up|configure|"
        r"notify|inform|alert|share|upload|download|install|restart|reset|migrate|"
        r"refactor|document|analyse|analyze|monitor|assign|close|open|merge|revert)\b",
        lower,
    ))
    if not has_verb:
        clarifications.append(f"What action should be performed in: '{action}'?")

    # Check for generic/vague objects
    if re.search(r"\b(issue|thing|stuff|something)\b", lower):
        clarifications.append(f"What specifically does '{action}' refer to?")

    # Check for vague method words
    if re.search(r"\b(somehow|anyhow)\b", lower):
        clarifications.append(f"How exactly should '{action}' be done?")

    # Check for vague pronoun "it" without a clear preceding noun
    it_match = re.search(r"\bit\b", lower)
    if it_match:
        before = lower[:it_match.start()].strip()
        words_before = before.split()
        last_word = words_before[-1].rstrip(".,;:") if words_before else ""
        if last_word not in _COMMON_NOUNS:
            clarifications.append("What does 'it' refer to?")

    return {
        "is_clear": len(clarifications) == 0,
        "clarifications": clarifications,
    }
