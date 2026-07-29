"""Detects mentions of non-technical (professional/soft) skills in free
text (worklog tasks/learnings/decisions).

This is the non-technical counterpart to tech_stack.py: same
dependency-light, deterministic keyword-matching philosophy, but against
a fixed vocabulary of general professional skills (communication,
leadership, mentoring, ...) rather than programming languages.

Same precision safeguard as skills_store.classify_skills_in_text:
requires at least 2 distinct keyword phrases to match, not just 1, so a
single coincidental word (e.g. "led" appearing in an unrelated sentence)
doesn't trigger a false positive on its own. Unlike that function, the
keyword lists here are hand-picked to already be mutually distinct
(no shared-keyword-across-skills problem to guard against), since each
soft skill's vocabulary was chosen deliberately rather than derived from
user-editable tags.
"""

import re

SOFT_SKILL_KEYWORDS: dict[str, list[str]] = {
    "Communication": ["communicat", "explained to", "presented to", "wrote up", "clarified"],
    "Stakeholder management": ["stakeholder", "buy-in", "aligned with", "expectations"],
    "Leadership": ["led the", "leadership", "owned the", "drove the"],
    "Mentoring": ["mentor", "coached", "onboarded", "paired with"],
    "Negotiation": ["negotiat", "compromise", "trade-off", "pushback"],
    "Prioritization": ["prioriti", "triaged", "backlog", "ranked the"],
    "Conflict resolution": ["conflict", "disagreement", "resolved the", "mediated"],
    "Time management": ["deadline", "time-box", "scheduled", "on time"],
}


def mentioned_soft_skills(text: str) -> set[str]:
    """Which soft skills are evidenced in `text`, requiring at least 2
    distinct keyword phrases per skill (not just 1 occurrence of 1
    phrase) to keep the signal precise enough to audit by hand."""
    text_lower = text.lower()
    matched = set()
    for skill, keywords in SOFT_SKILL_KEYWORDS.items():
        hits = {kw for kw in keywords if re.search(re.escape(kw), text_lower)}
        if len(hits) >= 2:
            matched.add(skill)
    return matched
