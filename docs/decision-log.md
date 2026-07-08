# Decision Log

Authorship and reasoning record for the AI Enablement System build, per the
"full authorship evidence from commit #1" guardrail. One entry per meaningful
decision, newest first.

## 2026-07-08 — Hand-rolled skill reader instead of fastmcp's Skills provider

**Context:** the build doc flagged that `fastmcp` (the standalone third-party
package, versions 3.0+) ships a built-in "Skills provider" and asked me to
evaluate it before hand-rolling a reader.

**Finding:** the pinned tech stack (`pip install "mcp[cli]"`) is the official
`mcp` SDK, whose `mcp.server.fastmcp.FastMCP` class is a different codebase
from the standalone `fastmcp` PyPI package that ships the Skills provider.
The installed `mcp` SDK (1.28.1) has no skill-loading feature at all.

**Decision:** hand-roll the reader (`skills_store.py`). Reasons:
- Adopting the Skills provider would mean swapping to a different framework
  than the one already decided, not just enabling a feature.
- The reader itself is a few lines of YAML-frontmatter parsing — a
  third-party provider buys negligible complexity reduction.
- Hand-rolling keeps the `list_skills` (light) / `get_skill` (heavy)
  boundary fully visible in our own code, which matters because that
  boundary is the exact thing this session needs to measure for the
  token-saving proposal.

## 2026-07-08 — Where usage logging happens

**Context:** `skill_usage` needs a row on every list and every fetch.

**Decision:** logging lives in `skills_store.py` (`log_usage`), called from
the thin tool wrappers in `server.py`. `get_skill` logs a `fetched` row even
when the name isn't found, so failed lookups are visible in analytics later
(e.g. "workers keep trying to fetch a skill that doesn't exist yet" is a
useful signal, not noise to discard).

## 2026-07-08 — Verifying without the MCP Inspector

**Context:** the build doc's checkpoints call for testing tools "with the MCP
Inspector," but Inspector is a browser UI and this session runs in a headless
remote container with no interactive browser.

**Decision:** verify each tool with the `mcp` Python client library directly
over stdio (`ClientSession` + `stdio_client`), which speaks the exact same
protocol Inspector uses under the hood. This gives the same pass/fail signal
("does the tool list, does it return the right thing") without requiring a
browser session.

## 2026-07-08 — Measuring the progressive-disclosure saving

**Context:** Phase 5's checkpoint asks to "compare the two output sizes and
record the difference" as the first metric for the proposal.

**Finding:** `list_skills` for all 6 skills (metadata only) is ~1.37KB.
Fetching all 6 full skill bodies would total ~4.74KB — about 3.5x more. In
practice a worker fetches the one or two skills relevant to their current
task, not all six, so the realistic per-task saving is larger than this
worst-case ratio suggests.
