# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Boolean and X-Ray search string builder for recruiting."""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


def _quote_term(term: str) -> str:
    term = term.strip()
    return f'"{term}"' if " " in term else term


def _or_group(terms: list[str]) -> str:
    quoted = [_quote_term(t) for t in terms if t.strip()]
    if not quoted:
        return ""
    if len(quoted) == 1:
        return quoted[0]
    return "(" + " OR ".join(quoted) + ")"


def _and_join(parts: list[str]) -> str:
    return " AND ".join(p for p in parts if p)


def build_boolean_search(
    role: str,
    skills: list[str],
    location: Optional[str] = None,
    exclude_terms: Optional[list[str]] = None,
    role_synonyms: Optional[list[str]] = None,
    experience_level: Optional[str] = None,
) -> dict:
    """Build Boolean and X-Ray search strings for LinkedIn, Google, and GitHub.

    Args:
      role: Primary role name (e.g. "Affiliate Manager")
      skills: List of key skills/technologies (e.g. ["iGaming", "CPA", "traffic"])
      location: Target location (e.g. "Ukraine", "Poland", "Remote")
      exclude_terms: Terms to exclude (e.g. ["intern", "junior"])
      role_synonyms: Alternative role titles (e.g. ["Partnership Manager"])
      experience_level: "junior", "mid", "senior", or None

    Returns: {linkedin_boolean, google_xray_linkedin, google_xray_github, github, tips}
    """
    all_roles = [role] + (role_synonyms or [])
    role_group = _or_group(all_roles)

    skills_group = _or_group(skills) if skills else ""

    level_terms: list[str] = []
    if experience_level:
        lvl = experience_level.lower()
        if lvl == "junior":
            level_terms = ["junior", "entry-level", "trainee"]
        elif lvl == "mid":
            level_terms = ["middle", "mid-level", "medior"]
        elif lvl == "senior":
            level_terms = ["senior", "lead", "head"]

    level_group = _or_group(level_terms) if level_terms else ""

    exclude_str = ""
    if exclude_terms:
        exclude_str = " ".join(f'-"{t}"' for t in exclude_terms if t.strip())

    # --- LinkedIn Boolean ---
    linkedin_parts = [role_group]
    if skills_group:
        linkedin_parts.append(skills_group)
    if location:
        linkedin_parts.append(_quote_term(location))
    if level_group:
        linkedin_parts.append(level_group)
    linkedin_boolean = _and_join(linkedin_parts)
    if exclude_str:
        linkedin_boolean += f" {exclude_str}"

    # --- Google X-Ray: LinkedIn profiles ---
    xray_parts = [f"site:linkedin.com/in", role_group]
    if skills_group:
        xray_parts.append(skills_group)
    if location:
        xray_parts.append(_quote_term(location))
    if level_group:
        xray_parts.append(level_group)
    google_xray_linkedin = " ".join(p for p in xray_parts if p)
    if exclude_str:
        google_xray_linkedin += f" {exclude_str}"

    # --- Google X-Ray: GitHub profiles ---
    github_skills = _or_group(skills) if skills else ""
    xray_github_parts = ["site:github.com"]
    if github_skills:
        xray_github_parts.append(github_skills)
    if location:
        xray_github_parts.append(_quote_term(location))
    google_xray_github = " ".join(p for p in xray_github_parts if p)

    # --- GitHub native search ---
    github_parts = []
    if location:
        github_parts.append(f'location:"{location}"')
    if skills:
        # GitHub search by language or topic
        github_parts.append(skills[0] if skills else "")
    github_search = "https://github.com/search?type=users&q=" + "+".join(
        p.replace('"', "%22").replace(":", "%3A").replace(" ", "+")
        for p in github_parts if p
    )

    tips = [
        f"LinkedIn: paste the Boolean string directly into LinkedIn search or Recruiter.",
        f"Google X-Ray (LinkedIn): use in Google search bar to find public LinkedIn profiles.",
        f"Google X-Ray (GitHub): finds GitHub profiles with matching skills in {location or 'any location'}.",
        f"GitHub: paste the URL or use github.com/search with location + language filters.",
        "Tip: combine X-Ray results with LinkedIn outreach for passive candidates.",
    ]
    if not skills:
        tips.append("Recommendation: add specific skills to narrow down results significantly.")

    result = {
        "role": role,
        "linkedin_boolean": linkedin_boolean,
        "google_xray_linkedin": google_xray_linkedin,
        "google_xray_github": google_xray_github,
        "github_search_url": github_search,
        "tips": tips,
    }
    log.info("boolean_builder: built strings for role='%s' location='%s'", role, location)
    return result
