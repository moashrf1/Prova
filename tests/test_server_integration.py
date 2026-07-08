"""End-to-end check of the actual MCP server process over stdio.

No MCP Inspector is available in this headless environment, so this uses
the mcp Python client library directly -- it speaks the same protocol
Inspector does, giving the same pass/fail signal for `list_skills` and
`get_skill` against the real skills/ content and data/enablement.db.
"""

import json
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.mark.asyncio
async def test_list_skills_and_get_skill_over_stdio():
    params = StdioServerParameters(
        command="python", args=["server.py"], cwd=str(PROJECT_ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = await session.call_tool("list_skills", {})
            skills = listed.structuredContent["result"]
            assert len(skills) == 6
            assert {s["name"] for s in skills} >= {
                "sql-query-optimization",
                "product-discovery",
            }
            for skill in skills:
                assert set(skill.keys()) == {
                    "name",
                    "title",
                    "description",
                    "category",
                    "path",
                }

            found = await session.call_tool(
                "get_skill", {"skill_name": "sql-query-optimization"}
            )
            assert "Indexes" in found.content[0].text

            missing = await session.call_tool(
                "get_skill", {"skill_name": "not-a-real-skill"}
            )
            assert "No skill named" in missing.content[0].text


@pytest.mark.asyncio
async def test_log_work_and_log_decision_over_stdio():
    """Same rationale as the skills test above: no Inspector available here,
    so the mcp client drives the real server process over stdio. Uses an
    identifiable project name since this writes into the real
    data/enablement.db (not isolated) -- consistent with how the
    list_skills/get_skill integration test already runs against real data."""
    params = StdioServerParameters(
        command="python", args=["server.py"], cwd=str(PROJECT_ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            decision = await session.call_tool(
                "log_decision",
                {
                    "project_name": "test-integration-project",
                    "decision": "Use stdio client for integration tests",
                    "reasoning": "No browser Inspector in this environment",
                    "rejected_alternative": "Skip integration coverage entirely",
                },
            )
            assert "Logged decision" in decision.content[0].text

            work = await session.call_tool(
                "log_work",
                {
                    "project_name": "test-integration-project",
                    "tasks": "wrote integration test",
                },
            )
            assert "Logged work" in work.content[0].text
