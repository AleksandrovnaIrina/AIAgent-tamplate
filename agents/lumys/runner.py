"""Lumys — general assistant runner (calendar, Gmail, reminders, memory)."""
import os
from agents.base_runner import AgentRunner, RunResult
from typing import Awaitable, Callable, Optional

_runner = AgentRunner(
    name="lumys",
    claude_md_path=os.environ.get("LUMYS_CLAUDE_MD", "/app/agents/lumys/CLAUDE.md"),
    mcp_servers={
        "memory": {"type": "http", "url": os.environ.get("MCP_MEMORY_URL", "http://mcp-memory:3100/mcp")},
        "hr":     {"type": "http", "url": os.environ.get("MCP_HR_URL",     "http://mcp-hr:3200/mcp")},
    },
    timeout=300,
)


async def run_turn(
    prompt: str,
    resume_session_id: Optional[str] = None,
    on_text_delta: Optional[Callable[[str], Awaitable[None]]] = None,
) -> RunResult:
    return await _runner.run_turn(prompt, resume_session_id, on_text_delta)
