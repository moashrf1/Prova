"""Detects mentions of programming languages/technologies in free text
(worklog tasks/learnings).

This is a distinct concept from skills_store.classify_skills_in_text: that
one matches against the curated skills library's own tags (methodology
topics like "sql-query-optimization"), while this one matches against a
fixed vocabulary of common languages/technologies (SQL the language, C#,
Python, ...) that aren't skill files at all. Same dependency-light,
deterministic philosophy as token_metrics.py and the skills classifier --
simple keyword matching, no LLM.

Known limitation: a few entries (Swift, Rust, Go) share their name with
common English words, so occasional false positives are possible for a
worklog entry that happens to use that word in an unrelated sense. This is
a lightweight signal for a personal dashboard, not a claim of certainty --
tighten a pattern below if a language starts showing up spuriously.
"""

import re

LANGUAGE_PATTERNS: dict[str, str] = {
    "Python": r"\bpython\b",
    "SQL": r"\bsql\b",
    "JavaScript": r"\bjavascript\b",
    "TypeScript": r"\btypescript\b",
    "C#": r"\bc#",
    "C++": r"\bc\+\+",
    "Java": r"\bjava\b",
    "Go": r"\bgolang\b",
    "Rust": r"\brust\b",
    "Ruby": r"\bruby\b",
    "PHP": r"\bphp\b",
    "Swift": r"\bswift\b",
    "Kotlin": r"\bkotlin\b",
    "HTML": r"\bhtml\b",
    "CSS": r"\bcss\b",
    "Bash": r"\bbash\b",
    "PowerShell": r"\bpowershell\b",
}


def mentioned_languages(text: str) -> set[str]:
    """Which languages/technologies are mentioned anywhere in `text`."""
    return {
        name
        for name, pattern in LANGUAGE_PATTERNS.items()
        if re.search(pattern, text, re.IGNORECASE)
    }
