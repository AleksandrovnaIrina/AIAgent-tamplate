# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""HTML → PDF via Playwright/Chromium, then upload to Google Drive."""
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

SIRIUS_DRIVE_FOLDER_ID = os.environ.get("SIRIUS_DRIVE_FOLDER_ID", "").strip() or None
PDF_TEMPLATES_DIR = Path(os.environ.get("SIRIUS_PDF_TEMPLATES_DIR", "/app/pdf_templates"))

_env = Environment(
    loader=FileSystemLoader(str(PDF_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


async def _render(html: str, out_path: str, page_format: str,
                  landscape: bool, margins: dict) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            await page.pdf(
                path=out_path,
                format=page_format,
                landscape=landscape,
                print_background=True,
                margin=margins,
            )
        finally:
            await browser.close()


def list_pdf_templates() -> list[dict]:
    """Return available PDF templates with their data-schema docstring."""
    if not PDF_TEMPLATES_DIR.is_dir():
        return []
    out = []
    for p in sorted(PDF_TEMPLATES_DIR.glob("*.html")):
        name = p.stem
        schema_path = PDF_TEMPLATES_DIR / f"{name}.md"
        doc = schema_path.read_text(encoding="utf-8") if schema_path.exists() else ""
        out.append({"name": name, "schema": doc.strip()})
    return out


def render_pdf_from_template(
    template_name: str,
    data: dict,
    name: str,
    page_format: str = "A4",
    landscape: bool = False,
    margin_mm: Optional[list[int]] = None,
) -> dict:
    """Render a Jinja2 PDF template with data and upload to Drive."""
    try:
        tpl = _env.get_template(f"{template_name}.html")
    except TemplateNotFound:
        avail = ", ".join(p.stem for p in PDF_TEMPLATES_DIR.glob("*.html"))
        raise ValueError(f"PDF template '{template_name}' not found. Available: {avail}")
    html = tpl.render(**(data or {}))
    return render_pdf(html=html, name=name, page_format=page_format,
                      landscape=landscape, margin_mm=margin_mm)


def render_pdf(html: str, name: str, page_format: str = "A4",
               landscape: bool = False,
               margin_mm: Optional[list[int]] = None) -> dict:
    if not name.lower().endswith(".pdf"):
        name = name + ".pdf"
    mm = margin_mm or [20, 15, 20, 15]
    margins = {
        "top": f"{mm[0]}mm",
        "right": f"{mm[1]}mm",
        "bottom": f"{mm[2]}mm",
        "left": f"{mm[3]}mm",
    }
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        out_path = tmp.name
    try:
        asyncio.run(_render(html, out_path, page_format, landscape, margins))
        size = Path(out_path).stat().st_size
        f = _drive_mod.upload(
            out_path, name=name, folder_id=SIRIUS_DRIVE_FOLDER_ID,
            mime="application/pdf", public=True,
        )
        log.info("pdf: rendered %s %d bytes → drive %s", name, size, f["id"])
        return {
            "drive_url": f.get("webViewLink"),
            "file_id": f["id"],
            "size_bytes": size,
            "name": f["name"],
        }
    finally:
        Path(out_path).unlink(missing_ok=True)
