# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""HTML+data → PNG banner via Playwright/Chromium, then upload to Drive.

Templates live in templates/<name>.html (Jinja2). Optional schema doc at
templates/<name>.md (markdown describing the data variables).
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
from playwright.async_api import async_playwright

import drive as _drive_mod

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(os.environ.get("SIRIUS_TEMPLATES_DIR", "/app/templates"))
SIRIUS_DRIVE_FOLDER_ID = os.environ.get("SIRIUS_DRIVE_FOLDER_ID", "").strip() or None

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def list_templates() -> list[dict]:
    """Return available banner templates with their data-schema docstring."""
    if not TEMPLATES_DIR.is_dir():
        return []
    out = []
    for p in sorted(TEMPLATES_DIR.glob("*.html")):
        name = p.stem
        schema_path = TEMPLATES_DIR / f"{name}.md"
        doc = schema_path.read_text(encoding="utf-8") if schema_path.exists() else ""
        out.append({"name": name, "schema": doc.strip()})
    return out


async def _render(template_name: str, data: dict, out_path: str,
                  width: int, height: int) -> None:
    try:
        tpl = _env.get_template(f"{template_name}.html")
    except TemplateNotFound:
        avail = ", ".join(p.stem for p in TEMPLATES_DIR.glob("*.html"))
        raise ValueError(f"template '{template_name}' not found. Available: {avail}")
    html = tpl.render(**(data or {}))
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        try:
            context = await browser.new_context(viewport={"width": width, "height": height})
            page = await context.new_page()
            await page.set_content(html, wait_until="networkidle")
            await page.screenshot(path=out_path, full_page=False, type="png")
        finally:
            await browser.close()


def render_banner(template_name: str, data: dict,
                  name: Optional[str] = None,
                  width: int = 1080, height: int = 1350) -> dict:
    import time
    if not name:
        name = f"{template_name}-{int(time.time())}.png"
    if not name.lower().endswith(".png"):
        name = name + ".png"
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        out_path = tmp.name
    try:
        asyncio.run(_render(template_name, data, out_path, width, height))
        f = _drive_mod.upload(
            out_path, name=name, folder_id=SIRIUS_DRIVE_FOLDER_ID,
            mime="image/png", public=True,
        )
        log.info("banner: rendered %s template=%s → drive %s", name, template_name, f["id"])
        return {
            "drive_url": f.get("webViewLink"),
            "file_id": f["id"],
            "name": f["name"],
        }
    finally:
        Path(out_path).unlink(missing_ok=True)
