"""Intent classifier — routes Telegram messages to the right specialized agent."""

import logging
import os
from typing import Literal

import anthropic

log = logging.getLogger("lumys.router")

ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "claude-haiku-4-5-20251001")
CLAUDE_CODE_OAUTH_TOKEN = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")

AgentName = Literal["scout", "argus", "sirius", "lumys"]

_SYSTEM = """\
Classify the user's message into exactly one category. Return ONLY one word, no punctuation.

Categories:
- scout   → HR, recruiting, sourcing, candidates, vacancy, interview, outreach, screening, \
Boolean search, X-Ray, LinkedIn candidates, Djinni, DOU, job description, salary, candidate tracking
- argus   → Instagram, competitors, reels, engagement, followers, content monitoring, \
competitor analysis, hook, transcript, reel caption, caption for Instagram
- sirius  → content creation, LinkedIn post, article, TikTok script, carousel, PDF, banner, \
lead magnet, Notion, YouTube summary, content plan, writing, repost, SMM
- lumys   → general assistant, memory, reminders, calendar, Gmail, anything else

Return exactly one word from the list above.
"""

# Simple keyword shortcuts to avoid API call for obvious cases
_KEYWORDS: dict[str, AgentName] = {
    # scout
    "boolean": "scout", "x-ray": "scout", "xray": "scout", "кандидат": "scout",
    "вакансія": "scout", "vacancy": "scout", "sourcing": "scout", "сорсинг": "scout",
    "аутріч": "scout", "outreach": "scout", "скрінінг": "scout", "screening": "scout",
    "djinni": "scout", "dou": "scout", "linkedin search": "scout", "job description": "scout",
    "рекрутинг": "scout", "recruiting": "scout", "інтерв'ю питання": "scout",
    # argus
    "instagram": "argus", "інстаграм": "argus", "reel": "argus", "рілс": "argus",
    "конкурент": "argus", "competitor": "argus", "caption": "argus",
    # sirius
    "linkedin пост": "sirius", "пост linkedin": "sirius", "пост для": "sirius",
    "карусель": "sirius", "carousel": "sirius", "tiktok": "sirius", "тікток": "sirius",
    "pdf": "sirius", "банер": "sirius", "banner": "sirius", "notion": "sirius",
    "контент-план": "sirius", "lead magnet": "sirius", "лід магніт": "sirius",
    "youtube": "sirius", "написати пост": "sirius", "постий": "sirius",
    # lumys
    "пошт": "lumys", "gmail": "lumys", "email": "lumys", "імейл": "lumys",
    "самарі пошти": "lumys", "листи": "lumys", "лист від": "lumys",
    "нагадай": "lumys", "нагадування": "lumys", "reminder": "lumys",
    "календар": "lumys", "calendar": "lumys", "зустріч": "lumys", "слот": "lumys",
    "пам'ять": "lumys", "запам'ятай": "lumys", "memory": "lumys",
    "/email": "lumys", "/new": "lumys",
}


def _keyword_route(message: str) -> AgentName | None:
    msg_lower = message.lower()
    for kw, agent in _KEYWORDS.items():
        if kw in msg_lower:
            return agent
    return None


async def classify(message: str, last_agent: AgentName | None = None) -> AgentName:
    """Classify user message and return the agent to handle it."""
    # Try fast keyword lookup first
    agent = _keyword_route(message)
    if agent:
        log.debug("keyword route → %s", agent)
        return agent

    # Fall back to LLM classification (haiku — fast + cheap)
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY") or CLAUDE_CODE_OAUTH_TOKEN or None
        client = anthropic.Anthropic(api_key=api_key)
        context = f"\nPrevious agent: {last_agent}" if last_agent else ""
        response = client.messages.create(
            model=ROUTER_MODEL,
            max_tokens=10,
            system=_SYSTEM,
            messages=[{"role": "user", "content": message + context}],
        )
        result = response.content[0].text.strip().lower().split()[0]
        if result in ("scout", "argus", "sirius", "lumys"):
            log.debug("LLM route → %s", result)
            return result  # type: ignore
    except Exception as e:
        log.warning("Router LLM failed: %s — falling back to last_agent or lumys", e)

    return last_agent or "lumys"
