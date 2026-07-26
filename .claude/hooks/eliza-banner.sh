#!/bin/bash
# Cosmetic-only SessionStart hook: welcomes the user as "Eliza" (this
# project's persona name, see CLAUDE.md) at the start of a new session,
# picking one of four designs at random each time for variety.
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
# is far more reliable here than color codes. The boxed design's interior
# padding was hand-computed with wcwidth (double-width emoji accounted
# for) during development so its borders line up -- the shipped hook has
# no such runtime dependency, only the already-verified literal strings.

python3 - <<'PYEOF'
import json
import random

BANNERS = [
    # Owl mascot
    (
        "✨🦉✨  E L I Z A  ✨🦉✨\n"
        "🟥🟧🟨🟩🟦🟪🟪🟦🟩🟨🟧🟥\n"
        "   your personal improvement agent\n"
        "🟥🟧🟨🟩🟦🟪🟪🟦🟩🟨🟧🟥"
    ),
    # Growth / progress theme
    (
        "📈  E L I Z A  📈\n"
        "▁▂▃▄▅▆▇█  growing a little more, every session  █▇▆▅▄▃▂▁"
    ),
    # Boxed + colorful (interior padding hand-verified with wcwidth for
    # double-width emoji, so the borders line up)
    (
        "╔════════════════════════════════════════════════╗\n"
        "║                                                ║\n"
        "║             ✨🌟  E L I Z A  🌟✨              ║\n"
        "║  🟪🟦🟩🟨🟧🟥 improvement agent 🟥🟧🟨🟩🟦🟪   ║\n"
        "║                                                ║\n"
        "╚════════════════════════════════════════════════╝"
    ),
    # Minimalist single line
    "🦉✨ Eliza's here — your personal improvement agent ✨🦉",
]

banner = random.choice(BANNERS)

instruction = (
    "This is the start of a brand-new Claude Code session in a project "
    "where you go by the name Eliza (see CLAUDE.md). Before addressing "
    "anything else in the user's first message this session, open your "
    "reply with exactly this welcome banner in its own fenced code block "
    "(so it renders unmodified, one line per line), then respond to the "
    "user's actual message normally below it:\n\n"
    f"```\n{banner}\n```\n\n"
    "Only do this once, for the very first reply of the session -- not on "
    "later turns."
)

print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": instruction,
}}))
PYEOF

exit 0
