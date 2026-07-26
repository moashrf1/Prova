#!/bin/bash
# Cosmetic-only SessionStart hook: welcomes the user as "Eliza" (this
# project's persona name, see CLAUDE.md) at the start of a new session.
#
# Claude Code's own startup splash (version, model, cwd, tips box) is a
# fixed built-in UI element -- no hook or setting can draw into it or
# replace it. `terminalSequence` can't substitute either: it's restricted
# to an allowlist of OSC notification/window-title/bell codes and silently
# drops anything else, including ANSI color codes and image protocols
# (OSC 1337 is explicitly on the reject list) -- confirmed against the
# hooks reference docs after an earlier version of this hook rendered
# nothing. So an actual image/GIF welcome isn't something this
# integration surface can do at all.
#
# The one thing a SessionStart hook actually controls is `additionalContext`
# -- plain text fed into Claude's own context before the first reply. So
# instead of trying to paint pixels ourselves, this asks Claude to open the
# session with a welcome message in its own reply, which the terminal
# renders like any other assistant text.
#
# Color comes from emoji glyphs, not ANSI escapes: terminals render emoji
# in full color via their own emoji font regardless of ANSI support, which
# is a much more reliable way to get a "colorful" banner than escape codes
# (which the box-lettered first version of this hook proved don't survive
# the additionalContext -> reply round trip visually anyway once inside a
# code fence). The owl mascot fits "Eliza" as a personal-improvement/
# mentor persona.

python3 - <<'PYEOF'
import json

BANNER = (
    "✨🦉✨  E L I Z A  ✨🦉✨\n"
    "🟥🟧🟨🟩🟦🟪🟪🟦🟩🟨🟧🟥\n"
    "   your personal improvement agent\n"
    "🟥🟧🟨🟩🟦🟪🟪🟦🟩🟨🟧🟥"
)

instruction = (
    "This is the start of a brand-new Claude Code session in a project "
    "where you go by the name Eliza (see CLAUDE.md). Before addressing "
    "anything else in the user's first message this session, open your "
    "reply with exactly this welcome banner in its own fenced code block "
    "(so it renders unmodified, one line per line), then respond to the "
    "user's actual message normally below it:\n\n"
    f"```\n{BANNER}\n```\n\n"
    "Only do this once, for the very first reply of the session -- not on "
    "later turns."
)

print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": instruction,
}}))
PYEOF

exit 0
