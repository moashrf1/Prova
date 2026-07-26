#!/bin/bash
# Cosmetic-only SessionStart hook: prints a colorful welcome banner for
# "Eliza" (this project's persona name, see CLAUDE.md).
#
# Plain stdout from a SessionStart hook is fed to Claude as context, never
# shown to the user -- making it visible in the terminal requires the JSON
# `terminalSequence` field instead, which Claude Code emits directly to the
# terminal on the hook's behalf. Built with python3 (stdlib json only, no
# project dependencies) so the ANSI escapes get JSON-encoded correctly
# rather than hand-escaped in bash.

python3 - <<'PYEOF'
import json

RESET = "\033[0m"
BOLD = "\033[1m"
COLORS = ["\033[31m", "\033[33m", "\033[32m", "\033[36m", "\033[35m"]
MAGENTA = "\033[35m"

rainbow_eliza = "".join(f"{c}{ch}" for c, ch in zip(COLORS, "ELIZA")) + RESET
bar = f"{MAGENTA}  ✨ {'─' * 46} ✨{RESET}"

banner = (
    "\n"
    f"{bar}\n"
    f"        {BOLD}{rainbow_eliza}   \U0001F4A1\n"
    f"     {BOLD}your personal improvement agent{RESET}\n"
    f"{bar}\n"
    "\n"
)

print(json.dumps({"terminalSequence": banner}))
PYEOF

exit 0
