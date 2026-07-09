"""Single source of truth for the token-estimation heuristic.

`tokens ≈ characters / 4` is a standard rough heuristic for English text.
Every call site that needs a token estimate routes through this module so
the assumption lives in one place and can be swapped for a real tokenizer
later without touching callers. Both chars and tokens_est are stored
wherever this is used, so the raw character counts survive any future
change of heuristic -- see docs/decision-log.md for the framing/heuristic
decisions this implements.
"""

CHARS_PER_TOKEN = 4


def estimate_tokens(chars: int) -> int:
    return chars // CHARS_PER_TOKEN


def measure(text: str) -> tuple[int, int]:
    """Return (chars, tokens_est) for a piece of served content."""
    chars = len(text)
    return chars, estimate_tokens(chars)
