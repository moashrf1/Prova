from mcp.server.fastmcp import FastMCP

import analytics_store
import repo_tech_store
import skills_store
import token_metrics
import work_store

mcp = FastMCP("ai-enablement")

skills_store.init_db()
work_store.init_db()
repo_tech_store.init_db()
skills_store.record_library_snapshot()


@mcp.tool()
def list_skills() -> list[dict]:
    """List all available skills with lightweight metadata only (no full content)."""
    skills = skills_store.load_all_skills()
    for skill in skills:
        chars, tokens_est = skills_store.measure_listing(skill)
        skills_store.log_usage(skill["name"], "listed", chars, tokens_est)
    return [
        {
            "name": skill["name"],
            "title": skill["title"],
            "description": skill["description"],
            "category": skill["category"],
            "path": skill["path"],
        }
        for skill in skills
    ]


@mcp.tool()
def get_skill(skill_name: str) -> str:
    """Fetch the full content of one skill by name (the heavy, on-demand layer)."""
    skill = skills_store.find_skill(skill_name)
    if skill is None:
        skills_store.log_usage(skill_name, "fetched")
        return f"No skill named '{skill_name}' was found. Use list_skills to see available skills."
    chars, tokens_est = token_metrics.measure(skill["body"])
    skills_store.log_usage(skill["name"], "fetched", chars, tokens_est)
    return skill["body"]


@mcp.tool()
def log_work(project_name: str, tasks: str, learnings: str | None = None) -> str:
    """Record an end-of-session worklog entry, auto-creating the project/session as needed."""
    result = work_store.log_work(project_name, tasks, learnings)
    return (
        f"Logged work for project '{result['project']}' "
        f"(project_id={result['project_id']}, session_id={result['session_id']}, "
        f"worklog_id={result['worklog_id']})."
    )


@mcp.tool()
def log_decision(
    project_name: str,
    decision: str,
    reasoning: str,
    rejected_alternative: str | None = None,
) -> str:
    """Record a single decision at the moment it's made, linked to the current session."""
    result = work_store.log_decision(project_name, decision, reasoning, rejected_alternative)
    return (
        f"Logged decision for project '{result['project']}' "
        f"(project_id={result['project_id']}, session_id={result['session_id']}, "
        f"decision_id={result['decision_id']})."
    )


@mcp.tool()
def scan_project_tech_stack(project_name: str, repo_path: str) -> list[dict]:
    """Scan a local git repository's commit history for source files by
    extension, and record the result as that project's tech-stack signal
    (replacing any previous scan for it).

    This is a structural signal, independent of worklog wording: a project
    whose worklog entries never happen to spell out "Python" or
    "JavaScript" still has a precise trail in its own repository -- the
    files it actually contains. repo_path must be a local path to a git
    repository with at least one commit, reachable from wherever this
    server is running. Returns the language/file_count breakdown found.
    """
    return repo_tech_store.record_repo_scan(project_name, repo_path)


@mcp.tool()
def learning_stats(path: str | None = None) -> dict:
    """Cumulative, all-time progress: total skills fetched, decisions, sessions.

    Pass a career path (e.g. "product-manager") to also get progress for
    that path's skills, read from the skill frontmatter's `path` field.
    Path progress counts a skill as "engaged with" if it was either
    explicitly fetched via get_skill, OR its keywords were detected in a
    worklog entry's tasks/learnings text (applied without re-fetching that
    session). `path_skills_fetched` and `path_skills_referenced_only`
    distinguish the two; `path_skill_engaged_count` is their union.
    """
    return analytics_store.compute_learning_stats(path)


@mcp.tool()
def token_report(period: str | None = None) -> dict:
    """How many context content tokens the skills library saved vs. loading
    the whole library up front (the counterfactual baseline).

    period: "weekly" (last 7 days), "monthly" (last 30 days), or omit for
    all-time cumulative. This measures server-side content size -- labeled
    "context content tokens (estimated)" -- not client-billed API tokens,
    which this server can't see.
    """
    return analytics_store.compute_token_report(period)


@mcp.tool()
def generate_recap(period: str) -> dict:
    """Temporal summary of recent work ("weekly" = last 7 days, "monthly" = last 30 days).

    Returns computed numbers plus the raw tasks/learnings/decisions text and
    a suggested framing line -- the tool does not write prose itself; turn
    this structured data into a short natural-language recap.
    """
    return analytics_store.compute_recap(period)


if __name__ == "__main__":
    mcp.run()
