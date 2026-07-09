# AI Enablement System — Master Build Document (Session 6)

Sessions 1–5 are complete (skills layer, worklog capture, analytics,
dashboard, orchestration). This session builds token measurement
instrumentation: the system measures, automatically and continuously, how
many tokens the skills library saves versus the naive alternative — so
every day of normal usage accumulates proposal evidence with zero extra
effort.

## 0. Where we are, and why this session

**Delivered (Sessions 1-5):** MCP server + six tools; five tables; three
store modules; read-only dashboard; three subagents orchestrated by the
main session; 41 passing tests; docs and decision log.

**The gap this session closes:** the project's headline promise is token
reduction via progressive disclosure, and the proposal needs that as a
number. This session instruments the system so the number produces itself
during normal use.

## 1. Measurement design

### What can honestly be measured

The MCP server can't see the client's actual billed API token usage. What
it can measure precisely is the size of the content it serves:

- **Actual cost**: size of `list_skills` output + sizes of only the skill
  bodies actually fetched.
- **Baseline (counterfactual)**: size of the whole library, as if it had
  all been loaded up front.
- **Saving**: baseline − actual.

Labeled everywhere as **"context content tokens (estimated)"**, never "API
tokens billed" — an honest, defensible metric is what makes it credible in
a proposal.

### Token estimation

`tokens_est = chars // 4`, implemented once in `token_metrics.py`. Both
`chars` and `tokens_est` are stored everywhere, so raw data survives any
future change of heuristic. A real tokenizer was deliberately skipped:
extra dependency, marginal accuracy gain on a comparative metric where both
sides use the identical heuristic.

### Storage

- `skill_usage` extended additively (`ALTER TABLE ... ADD COLUMN`) with
  `chars`, `tokens_est` — nullable for historical rows, always populated
  for new ones.
- New `library_snapshots` table: a snapshot of the full library's size,
  recorded on server start but only when it changed since the last one.

## 2. What was built

- **Phase 1**: `token_metrics.py` (the shared heuristic); additive
  migration + `measure_listing()`/`record_library_snapshot()` in
  `skills_store.py`; `list_skills`/`get_skill` now record real sizes;
  server startup snapshots the library.
- **Phase 2**: `compute_token_report(period)` in `analytics_store.py`
  (actual vs. baseline vs. saving, weekly/monthly/cumulative); the
  `token_report` MCP tool.
- **Phase 3**: a `token_saving` block added to `generate_recap`;
  `GET /api/token-report`; a prominent "Token savings" card at the top of
  the dashboard (headline percentage synced to the weekly/monthly toggle,
  plus a This-week/This-month/All-time comparison chart), with the honest
  "context content tokens (estimated)... not client-billed API tokens"
  label always visible.
- **Phase 4**: 23 new tests (64 total); README's honest framing section;
  this doc.

## 3. What was caught during verification (not just assumed)

- A real rounding-consistency bug: aggregate `tokens_est` was first
  computed by summing already floor-divided per-row estimates, which
  drifts from flooring the summed `chars` once (the way the baseline is
  computed) — 527 vs. the correct 529 on real seeded data. Fixed by
  deriving every aggregate from summed `chars` via
  `token_metrics.estimate_tokens()`, matching the baseline's method
  exactly. Caught by hand-computing the expected saving independently and
  comparing, not by inspection.
- Migration additivity confirmed against a simulated pre-Session-6
  database: old row survived with `NULL` sizes, `init_db()` idempotent
  across repeated calls.
- Snapshot dedup confirmed: 3 calls against an unchanged library produced
  1 row; a genuine library change produced a 2nd.
- Dashboard/API/tool agreement confirmed for both weekly and monthly: all
  three surfaces returned identical numbers for seeded data.

## 4. Explicitly NOT in this session

- A real tokenizer dependency.
- Measuring client-side/API billed tokens (not visible from the server).
- Any new company-version features; calendar; other-people's paths.

## 5. After this session

Every normal working day now automatically strengthens the proposal:
usage accumulates, the saving number grows, and the dashboard displays it.
The sensible next milestone is not more building — it's 2-3 weeks of real
daily use, then packaging the accumulated evidence into the internal
business proposal.
