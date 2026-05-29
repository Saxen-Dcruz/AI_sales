"""
LinkedIn Lead Scraper — delegates to the LinkdenScrapper Node.js microservice.

The Node.js service (D:/projects/LinkdenScrapper) runs Playwright searches at
POST /search-leads and returns structured lead data. This service calls it via
HTTP, maps the response into ProspectCompany + ProspectContact DB records, and
optionally runs AI scoring.

Flow:
  1. For each target_role, POST /search-leads to the Node.js scraper
  2. Map response fields (camelCase → snake_case)
  3. Infer company from jobTitle headline
  4. Upsert ProspectCompany + ProspectContact
  5. Run AI scoring batch
"""
import asyncio
import logging
import re
from typing import Optional
from uuid import UUID

from pathlib import Path

import httpx

from app.core.config import settings
from app.database.core import SessionLocal
from app.models.lead_gen import ProspectCompany, ProspectContact

logger = logging.getLogger("rdl_app_logger")

SCRAPER_URL = settings.LINKEDIN_SCRAPER_URL

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_LI_AT_FILE   = _BACKEND_ROOT / "linkedin_profile_context" / "li_at.txt"


def _read_li_at() -> str:
    """Read the li_at cookie value saved via the Settings UI."""
    if _LI_AT_FILE.exists():
        val = _LI_AT_FILE.read_text(encoding="utf-8").strip()
        if val:
            return val
    return ""


# ── HTTP call to Node.js scraper ──────────────────────────────────────────────

def _call_scraper(keyword: str, title: str, location: str, limit: int) -> list[dict]:
    """
    POST /search-leads to the LinkdenScrapper Node.js service.
    Returns a list of lead dicts with keys: name, jobTitle, location, profileUrl, connectionDegree
    """
    li_at = _read_li_at()
    if not li_at:
        logger.warning("[LI SCRAPER] No li_at cookie found — scraper will run unauthenticated")

    payload = {
        "keyword": keyword,
        "title": title,
        "location": location,
        "limit": limit,
        "li_at": li_at,
    }
    try:
        resp = httpx.post(
            f"{SCRAPER_URL}/search-leads",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        leads = data.get("leads", [])
        logger.info(f"[LI SCRAPER] keyword='{keyword}' title='{title}' → {len(leads)} leads from scraper")
        return leads
    except httpx.HTTPStatusError as e:
        logger.error(f"[LI SCRAPER] HTTP error from scraper: {e.response.status_code} — {e.response.text[:200]}")
    except httpx.RequestError as e:
        logger.error(f"[LI SCRAPER] Could not reach scraper at {SCRAPER_URL}: {e}")
    return []


# ── Field mapping ─────────────────────────────────────────────────────────────

def _map_lead(raw: dict) -> dict:
    """Map LinkdenScrapper camelCase fields to the internal snake_case format."""
    return {
        "name": (raw.get("name") or "").strip(),
        "job_title": (raw.get("jobTitle") or "").strip(),
        "location": (raw.get("location") or "").strip(),
        "linkedin_url": (raw.get("profileUrl") or "").strip(),
        "connection_degree": raw.get("connectionDegree", "3rd+"),
    }


# ── Company inference ─────────────────────────────────────────────────────────

def _infer_company_from_headline(headline: str) -> Optional[str]:
    """Extract company name from headline like 'Senior Manager at Tata Steel'."""
    if not headline:
        return None
    match = re.search(r'\bat\s+(.+?)(?:\s*[\|·,]|$)', headline, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


# ── DB helpers ────────────────────────────────────────────────────────────────

def _upsert_company(db, name: str, industry: str = "", location: str = "") -> Optional[ProspectCompany]:
    name = name.strip()
    if not name:
        return None
    existing = db.query(ProspectCompany).filter(ProspectCompany.name.ilike(name)).first()
    if existing:
        # Backfill industry/location if they were missing
        if industry and not existing.industry:
            existing.industry = industry.strip().lower()
        if location and not existing.location:
            existing.location = location
        return existing
    company = ProspectCompany(
        name=name,
        industry=industry.strip().lower() if industry else None,
        location=location or None,
        source="linkedin_scrape",
    )
    db.add(company)
    db.flush()
    return company


def _upsert_contact(db, company_id: UUID, data: dict) -> Optional[ProspectContact]:
    name = (data.get("name") or "").strip()
    if not name:
        return None
    existing = db.query(ProspectContact).filter(
        ProspectContact.company_id == company_id,
        ProspectContact.name.ilike(name),
    ).first()
    if existing:
        if not existing.linkedin_url and data.get("linkedin_url"):
            existing.linkedin_url = data["linkedin_url"]
        return existing
    contact = ProspectContact(
        company_id=company_id,
        name=name,
        job_title=data.get("job_title") or None,
        linkedin_url=data.get("linkedin_url") or None,
    )
    db.add(contact)
    db.flush()
    return contact


# ── Main entry points ─────────────────────────────────────────────────────────

async def run_linkedin_scrape(
    keyword: str,
    location: str = "India",
    target_roles: list[str] | None = None,
    max_results: int = 20,
) -> dict:
    """
    Main entry point called by the API endpoint.
    Calls LinkdenScrapper once per role, saves results to DB.
    """
    target_roles = target_roles or ["Manager", "Director", "CEO", "Operations", "Procurement"]

    result = {
        "status": "ok",
        "companies_found": 0,
        "contacts_found": 0,
        "errors": [],
    }

    db = SessionLocal()
    try:
        per_role = max(1, max_results // len(target_roles))

        for i, role in enumerate(target_roles):
            if i > 0:
                # 45-second cooldown between role searches to avoid LinkedIn bot detection
                await asyncio.sleep(45)

            raw_leads = _call_scraper(keyword, role, location, per_role)

            for raw in raw_leads:
                lead = _map_lead(raw)
                if not lead["name"]:
                    continue

                company_name = _infer_company_from_headline(lead["job_title"])
                if not company_name:
                    company_name = f"{keyword.title()} Company"

                company = _upsert_company(db, company_name, industry=keyword, location=lead["location"])
                if not company:
                    continue
                result["companies_found"] += 1

                contact = _upsert_contact(db, company.id, lead)
                if contact:
                    result["contacts_found"] += 1

        db.commit()
        logger.info(f"[LI SCRAPER] Done — contacts={result['contacts_found']}")

        try:
            from app.services.ai_lead_scorer import batch_score_companies
            batch_score_companies(db)
        except Exception as e:
            logger.warning(f"[LI SCRAPER] Scoring skipped: {e}")

    except Exception as e:
        logger.error(f"[LI SCRAPER] Fatal: {e}", exc_info=True)
        result["status"] = "error"
        result["errors"].append(str(e))
    finally:
        db.close()

    return result


async def run_auto_search(searches: list[dict]) -> dict:
    """
    Auto-search entry point called by the poller.
    `searches` is a list of {keyword, location, roles, max_results}.
    """
    totals = {"contacts_found": 0, "errors": []}

    db = SessionLocal()
    try:
        for s in searches:
            keyword = s.get("keyword", "")
            location = s.get("location", "India")
            roles = s.get("roles") or ["Manager", "Director", "CEO"]
            limit = s.get("max_results", 10)
            per_role = max(1, limit // len(roles))

            logger.info(f"[LI AUTO] Searching '{keyword}' in '{location}'")

            for j, role in enumerate(roles):
                if j > 0:
                    await asyncio.sleep(45)

                raw_leads = _call_scraper(keyword, role, location, per_role)

                for raw in raw_leads:
                    lead = _map_lead(raw)
                    if not lead["name"]:
                        continue
                    company_name = _infer_company_from_headline(lead["job_title"]) or f"{keyword.title()} Company"
                    company = _upsert_company(db, company_name, industry=keyword, location=lead["location"])
                    if not company:
                        continue
                    contact = _upsert_contact(db, company.id, lead)
                    if contact:
                        totals["contacts_found"] += 1

        db.commit()
        logger.info(f"[LI AUTO] Total contacts found: {totals['contacts_found']}")

        try:
            from app.services.ai_lead_scorer import batch_score_companies
            batch_score_companies(db)
        except Exception as e:
            logger.warning(f"[LI AUTO] Scoring skipped: {e}")

    except Exception as e:
        logger.error(f"[LI AUTO] Fatal: {e}", exc_info=True)
        totals["errors"].append(str(e))
    finally:
        db.close()

    return totals


# ── Default auto-search config ────────────────────────────────────────────────

DEFAULT_AUTO_SEARCHES = [
    {"keyword": "manufacturing",         "location": "India", "roles": ["Plant Manager", "Operations Head", "Procurement Manager", "CEO"],       "max_results": 15},
    {"keyword": "industrial automation", "location": "India", "roles": ["Automation Engineer", "Plant Head", "Technical Director"],              "max_results": 10},
    {"keyword": "logistics",             "location": "India", "roles": ["Operations Manager", "Supply Chain Head", "Logistics Director"],        "max_results": 10},
    {"keyword": "oil gas energy",        "location": "India", "roles": ["Plant Manager", "Operations Director", "Instrumentation Engineer"],     "max_results": 10},
    {"keyword": "pharma",                "location": "India", "roles": ["Production Manager", "Plant Head", "Quality Director"],                 "max_results": 10},
]
