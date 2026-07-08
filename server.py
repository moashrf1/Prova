from mcp.server.fastmcp import FastMCP

import skills_store

mcp = FastMCP("ai-enablement")

skills_store.init_db()


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


if __name__ == "__main__":
    mcp.run()
