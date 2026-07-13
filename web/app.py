"""Read-only web dashboard over the accumulated enablement data.

This is a second entry point onto the same data/enablement.db that
server.py's MCP tools write to -- it never writes. All query logic is
reused from analytics_store.py (whose connections are already read-only
at the SQLite level; see that module's docstring), so nothing here
duplicates a query that already exists and is already tested.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import analytics_store  # noqa: E402

app = FastAPI(title="AI Enablement Dashboard")


def _run_readonly(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/recap")
def get_recap(period: str = "weekly"):
    if period not in analytics_store.PERIOD_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {list(analytics_store.PERIOD_WINDOWS)}",
        )
    return _run_readonly(analytics_store.compute_recap, period)


@app.get("/api/learning-stats")
def get_learning_stats(path: str | None = None):
    return _run_readonly(analytics_store.compute_learning_stats, path)


@app.get("/api/projects")
def get_projects():
    return _run_readonly(analytics_store.project_rollups)


@app.get("/api/decisions")
def get_decisions(limit: int = 20):
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be at least 1")
    return _run_readonly(analytics_store.recent_decisions, limit)


@app.get("/api/skills")
def get_skills():
    return _run_readonly(analytics_store.skill_usage_counts)


@app.get("/api/skill-engagement")
def get_skill_engagement():
    return _run_readonly(analytics_store.skill_engagement_overview)


@app.get("/api/tech-stack")
def get_tech_stack():
    return _run_readonly(analytics_store.tech_stack_usage)


@app.get("/api/token-report")
def get_token_report(period: str | None = None):
    if period is not None and period not in analytics_store.PERIOD_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {list(analytics_store.PERIOD_WINDOWS)}, or omitted for cumulative",
        )
    return _run_readonly(analytics_store.compute_token_report, period)


app.mount("/", StaticFiles(directory=str(PROJECT_ROOT / "static"), html=True), name="static")
