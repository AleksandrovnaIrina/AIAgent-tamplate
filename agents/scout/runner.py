# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Scout — HR & recruiting agent runner."""
import os
from agents.base_runner import AgentRunner, RunResult
from typing import Awaitable, Callable, Optional

_runner = AgentRunner(
    name="scout",
    claude_md_path=os.environ.get("SCOUT_CLAUDE_MD", "/app/agents/scout/CLAUDE.md"),
    mcp_servers={
        "memory": {"type": "http", "url": os.environ.get("MCP_MEMORY_URL", "http://mcp-memory:3100/mcp")},
        "scout":  {"type": "http", "url": os.environ.get("MCP_SCOUT_URL",  "http://mcp-scout:3400/mcp")},
    },
    timeout=300,
)


async def run_turn(
    prompt: str,
    resume_session_id: Optional[str] = None,
    on_text_delta: Optional[Callable[[str], Awaitable[None]]] = None,
) -> RunResult:
    return await _runner.run_turn(prompt, resume_session_id, on_text_delta)
