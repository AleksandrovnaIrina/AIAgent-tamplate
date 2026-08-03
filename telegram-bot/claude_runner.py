# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Bridges Telegram messages to the Claude Agent SDK with two MCP servers."""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from anthropic import Anthropic
from claude_agent_sdk import AgentRunner, MCPServerHTTP, RunResult

log = logging.getLogger("lumys.claude")

CLAUDE_MD_PATH = os.environ.get("CLAUDE_MD_PATH", "/app/CLAUDE.md")
MCP_MEMORY_URL = os.environ.get("MCP_MEMORY_URL", "http://mcp-memory:3100/mcp")
MCP_HR_URL = os.environ.get("MCP_HR_URL", "http://mcp-hr:3200/mcp")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_MAX_TURNS = int(os.environ.get("CLAUDE_MAX_TURNS", "20"))
CLAUDE_TIMEOUT_SECONDS = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "300"))


def _load_system_prompt() -> str:
    try:
        with open(CLAUDE_MD_PATH) as f:
            return f.read()
    except FileNotFoundError:
        log.warning("CLAUDE.md not found at %s", CLAUDE_MD_PATH)
        return "You are LumysAgent, a personal HR and recruiting assistant."


async def run_turn(
    prompt: str,
    resume_session_id: Optional[str] = None,
    on_text_delta: Optional[Callable[[str], Awaitable[None]]] = None,
) -> RunResult:
    """Execute one conversation turn with Claude + MCP tools."""
    system_prompt = _load_system_prompt()

    mcp_servers = [
        MCPServerHTTP(url=MCP_MEMORY_URL),
        MCPServerHTTP(url=MCP_HR_URL),
    ]

    runner = AgentRunner(
        model=CLAUDE_MODEL,
        system_prompt=system_prompt,
        mcp_servers=mcp_servers,
        max_turns=CLAUDE_MAX_TURNS,
    )

    try:
        result = await asyncio.wait_for(
            runner.run(
                prompt=prompt,
                session_id=resume_session_id,
                on_text_delta=on_text_delta,
            ),
            timeout=CLAUDE_TIMEOUT_SECONDS,
        )
        return result
    except asyncio.TimeoutError:
        log.warning("Claude turn timed out after %ds", CLAUDE_TIMEOUT_SECONDS)
        return RunResult(
            content="⏱ Час очікування вийшов. Спробуй ще раз або спрости запит.",
            session_id=resume_session_id,
            error="timeout",
        )
    except Exception as e:
        log.exception("Claude turn failed")
        return RunResult(
            content=f"⚠️ Помилка: {e}",
            session_id=resume_session_id,
            error=str(e),
        )
