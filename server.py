from mcp.server.fastmcp import FastMCP

import skills_store
import work_store

mcp = FastMCP("ai-enablement")

skills_store.init_db()
work_store.init_db()


@mcp.tool()
def list_skills() -> list[dict]:
    """List all available skills with lightweight metadata only (no full content)."""
    skills = skills_store.load_all_skills()
    for skill in skills:
        skills_store.log_usage(skill["name"], "listed")
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
    skills_store.log_usage(skill["name"], "fetched")
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


if __name__ == "__main__":
    mcp.run()
