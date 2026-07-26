#!/bin/bash
# Cosmetic-only SessionStart hook: prints a colorful welcome banner for
# "Eliza" (this project's persona name, see CLAUDE.md). Never blocks
# session start -- always exits 0 regardless of terminal color support.

RESET='\033[0m'
BOLD='\033[1m'
RED='\033[31m'
YELLOW='\033[33m'
GREEN='\033[32m'
CYAN='\033[36m'
MAGENTA='\033[35m'

printf "\n"
printf "${MAGENTA}  ✨ ────────────────────────────────────────── ✨${RESET}\n"
printf "        ${BOLD}${RED}E${YELLOW}L${GREEN}I${CYAN}Z${MAGENTA}A${RESET}   💡\n"
printf "     ${BOLD}your personal improvement agent${RESET}\n"
printf "${MAGENTA}  ✨ ────────────────────────────────────────── ✨${RESET}\n"
printf "\n"

exit 0
