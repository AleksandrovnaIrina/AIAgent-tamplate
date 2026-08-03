# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Shared Claude Agent SDK runner — parametrized per agent."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)
from claude_agent_sdk.types import StreamEvent

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_MAX_TURNS = int(os.environ.get("CLAUDE_MAX_TURNS", "20"))

_RATE_LIMIT_KEYWORDS = (
    "rate limit", "429", "quota exceeded", "too many requests",
    "overloaded", "usage limit", "credit",
)


@dataclass
class RunResult:
    content: str
    session_id: Optional[str]
    error: Optional[str] = None


def _load_tokens() -> list[str]:
    tokens: list[str] = []
    for i in range(1, 10):
        t = os.environ.get(f"CLAUDE_TOKEN_{i}", "").strip()
        if t:
            tokens.append(t)
    if not tokens:
        primary = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
        for t in primary.split(","):
            if t.strip():
                tokens.append(t.strip())
        for i in range(2, 20):
            t = os.environ.get(f"CLAUDE_CODE_OAUTH_TOKEN_{i}", "").strip()
            if t:
                tokens.append(t)
    return tokens or [""]


_TOKENS = _load_tokens()
_token_idx = 0
_token_lock = threading.Lock()


def _current_token() -> str:
    with _token_lock:
        return _TOKENS[_token_idx]


def _rotate_token() -> None:
    global _token_idx
    with _token_lock:
        _token_idx = (_token_idx + 1) % len(_TOKENS)


def _is_rate_limit(error: str) -> bool:
    return any(kw in error.lower() for kw in _RATE_LIMIT_KEYWORDS)


class AgentRunner:
    """Reusable Claude runner for a specific agent configuration."""

    def __init__(
        self,
        name: str,
        claude_md_path: str,
        mcp_servers: dict,
        timeout: int = 300,
    ):
        self.name = name
        self.claude_md_path = Path(claude_md_path)
        self.mcp_servers = mcp_servers
        self.timeout = timeout
        self.log = logging.getLogger(f"lumys.{name}")

    def _load_prompt(self) -> str:
        if self.claude_md_path.exists():
            return self.claude_md_path.read_text(encoding="utf-8")
        self.log.warning("CLAUDE.md not found at %s", self.claude_md_path)
        return f"You are {self.name}, an AI assistant. Reply in Ukrainian."

    def _make_options(
        self,
        token: str,
        resume_session_id: Optional[str],
        on_text_delta,
    ) -> ClaudeAgentOptions:
        opts = ClaudeAgentOptions(
            max_turns=CLAUDE_MAX_TURNS,
            model=CLAUDE_MODEL,
            system_prompt=self._load_prompt(),
            mcp_servers=self.mcp_servers,
            permission_mode="bypassPermissions",
            include_partial_messages=on_text_delta is not None,
            cwd="/app",
        )
        if token:
            opts.env = {"CLAUDE_CODE_OAUTH_TOKEN": token}
        if resume_session_id:
            opts.resume = resume_session_id
        return opts

    async def run_turn(
        self,
        prompt: str,
        resume_session_id: Optional[str] = None,
        on_text_delta: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> RunResult:
        attempts = len(_TOKENS)
        last_error: Optional[str] = None

        for attempt in range(attempts):
            token = _current_token()
            text_parts: list[str] = []
            session_id: Optional[str] = None
            options = self._make_options(token, resume_session_id, on_text_delta)

            async def _run() -> None:
                nonlocal session_id
                client = ClaudeSDKClient(options)
                try:
                    await client.connect()
                    await client.query(prompt)
                    async for message in client.receive_messages():
                        if isinstance(message, ResultMessage):
                            session_id = getattr(message, "session_id", None) or session_id
                            result = getattr(message, "result", None)
                            if result:
                                text_parts.append(str(result))
                            break

                        msg_sid = getattr(message, "session_id", None)
                        if msg_sid:
                            session_id = msg_sid

                        if on_text_delta and isinstance(message, StreamEvent):
                            event = message.event or {}
                            if event.get("type") == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    chunk = delta.get("text", "")
                                    if chunk:
                                        await on_text_delta(chunk)

                        if isinstance(message, AssistantMessage):
                            for block in (getattr(message, "content", []) or []):
                                if isinstance(block, TextBlock):
                                    text_parts.append(block.text)
                finally:
                    await client.disconnect()

            try:
                await asyncio.wait_for(_run(), timeout=self.timeout)
            except asyncio.TimeoutError:
                return RunResult(
                    content=f"⏱ {self.name} тайм-аут — спробуй ще раз.",
                    session_id=session_id,
                    error="timeout",
                )
            except Exception as exc:
                err_str = str(exc)
                last_error = err_str
                if _is_rate_limit(err_str) and len(_TOKENS) > 1:
                    self.log.warning("Rate limit — rotating token (attempt %d/%d)", attempt + 1, attempts)
                    _rotate_token()
                    resume_session_id = None
                    continue
                if "exit code 1" in err_str and resume_session_id:
                    self.log.warning("Exit code 1 with session — retrying without session")
                    resume_session_id = None
                    continue
                self.log.exception("Claude turn failed")
                return RunResult(content=f"⚠️ Помилка: {exc}", session_id=session_id, error=err_str)

            final_text = ""
            for chunk in text_parts:
                if chunk and chunk not in final_text:
                    final_text = (final_text + "\n" + chunk).strip() if final_text else chunk
            return RunResult(content=final_text or "(no response)", session_id=session_id)

        return RunResult(
            content="Всі Claude акаунти досягли ліміту. Спробуй пізніше.",
            session_id=None,
            error=last_error,
        )
