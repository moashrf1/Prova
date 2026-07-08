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


if __name__ == "__main__":
    mcp.run()
