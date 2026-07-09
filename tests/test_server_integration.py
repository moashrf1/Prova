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


@pytest.mark.asyncio
async def test_generate_recap_and_learning_stats_over_stdio():
    """Same no-Inspector rationale as above. Runs against the real
    data/enablement.db, which by this point in the suite has at least the
    test-integration-project work logged by the test above -- just checks
    the tools respond with well-formed, self-consistent data, not exact
    counts (those are covered precisely by test_analytics_store.py's
    isolated fixtures)."""
    params = StdioServerParameters(
        command="python", args=["server.py"], cwd=str(PROJECT_ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            recap = await session.call_tool("generate_recap", {"period": "weekly"})
            recap_data = json.loads(recap.content[0].text)
            assert recap_data["session_count"] >= 1
            assert "test-integration-project" in recap_data["projects_touched"]

            stats = await session.call_tool("learning_stats", {"path": "product-manager"})
            stats_data = json.loads(stats.content[0].text)
            assert stats_data["path_skill_total"] == 3
            assert 0 <= stats_data["path_skill_fetched_count"] <= 3


@pytest.mark.asyncio
async def test_token_report_over_stdio_and_recap_agreement():
    """Same no-Inspector rationale as above. Server startup calls
    record_library_snapshot(), so a baseline exists by the time any tool
    call happens -- confirms token_report and generate_recap's
    token_saving block report the identical numbers for the same period,
    which is the Phase 3 checkpoint (dashboard/API/tool all agreeing)."""
    params = StdioServerParameters(
        command="python", args=["server.py"], cwd=str(PROJECT_ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            await session.call_tool("list_skills", {})

            report = await session.call_tool("token_report", {"period": "weekly"})
            report_data = json.loads(report.content[0].text)
            assert report_data["baseline_tokens_est"] is not None
            assert report_data["actual_tokens_est"] >= 0
            assert "context content tokens" in report_data["label"]

            recap = await session.call_tool("generate_recap", {"period": "weekly"})
            recap_data = json.loads(recap.content[0].text)
            assert recap_data["token_saving"]["baseline_tokens_est"] == report_data["baseline_tokens_est"]
            assert recap_data["token_saving"]["saving_tokens_est"] == report_data["saving_tokens_est"]

            cumulative = await session.call_tool("token_report", {})
            cumulative_data = json.loads(cumulative.content[0].text)
            assert cumulative_data["period"] is None
