#!/bin/bash
# Cosmetic-only SessionStart hook: welcomes the user as "Eliza" (this
# project's persona name, see CLAUDE.md) at the start of a new session.
#
# Claude Code's own startup splash (version, model, cwd, tips box) is a
# fixed built-in UI element -- no hook or setting can draw into it or
# replace it. `terminalSequence` (tried in an earlier version of this
# hook) can't substitute either: it's restricted to an allowlist of OSC
# notification/window-title/bell codes and silently drops anything else,
# including the ANSI color codes a banner needs -- confirmed against the
# hooks reference docs after the first attempt rendered nothing.
#
# The one thing a SessionStart hook actually controls is `additionalContext`
# -- plain text fed into Claude's own context before the first reply. So
# instead of trying to paint pixels ourselves, this asks Claude to open the
# session with a short welcome message in its own reply, which the terminal
# renders like any other assistant text (markdown, code-block monospacing
# for the box art included) -- not identical to the native splash, but the
# closest real equivalent this integration surface supports.

python3 - <<'PYEOF'
import json

WIDTH = 40
title = "E L I Z A"
subtitle = "your personal improvement agent"

def center(text: str) -> str:
    return f"│{text.center(WIDTH)}│"

box = "\n".join([
    f"┌{'─' * WIDTH}┐",
    center(""),
    center(title),
    center(subtitle),
    center(""),
    f"└{'─' * WIDTH}┘",
])

instruction = (
    "This is the start of a brand-new Claude Code session in a project "
    "where you go by the name Eliza (see CLAUDE.md). Before addressing "
    "anything else in the user's first message this session, open your "
    "reply with exactly this welcome banner in its own fenced code block "
    "(so it renders as monospace, unmodified), then respond to the user's "
    "actual message normally below it:\n\n"
    f"```\n{box}\n```\n\n"
    "Only do this once, for the very first reply of the session -- not on "
    "later turns."
)

print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": instruction,
}}))
PYEOF

exit 0
