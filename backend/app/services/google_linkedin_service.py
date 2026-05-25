"""
LinkedIn profile discovery via Google Custom Search API.

Queries: site:linkedin.com/in/ "{role}" "{keyword}" "{location}"
No LinkedIn login required — uses Google's search index.

One-time setup:
  1. Go to https://programmablesearchengine.google.com/
  2. Click "Add" → give it any name → set "Search the entire web" → Create
  3. Copy the Search engine ID (looks like "abc123:xyz")
  4. In Google Cloud Console, enable "Custom Search API" for your project
  5. Add GOOGLE_CSE_ID=<that id> to .env.local
  6. Restart backend
"""
import logging
import re
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.core import SessionLocal
from app.models.lead_gen import ProspectCompany, ProspectContact

logger = logging.getLogger("rdl_app_logger")

_CSE_URL = "https://www.googleapis.com/customsearch/v1"


# ── Google search ─────────────────────────────────────────────────────────────

def _google_search(query: str, num: int = 10) -> list[dict]:
    if not settings.GOOGLE_API_KEY:
        logger.warning("[GOOG LI] GOOGLE_API_KEY not set")
        return []
    if not settings.GOOGLE_CSE_ID:
        logger.warning("[GOOG LI] GOOGLE_CSE_ID not set — see module docstring for setup")
        return []
    try:
        resp = httpx.get(
            _CSE_URL,
            params={
                "key": settings.GOOGLE_API_KEY,
                "cx": settings.GOOGLE_CSE_ID,
                "q": query,
                "num": min(num, 10),
            },
            timeout=12,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        logger.error(f"[GOOG LI] Search error: {e}")
        return []


# ── Result parsing ─────────────────────────────────────────────────────────────

def _parse_profile(item: dict) -> Optional[dict]:
    """
    Extract structured data from a Google CSE result for a LinkedIn /in/ URL.

    Typical result:
      title:   "John Smith - CEO at Mahindra Logistics | LinkedIn"
      link:    "https://www.linkedin.com/in/john-smith-abc/"
      snippet: "CEO at Mahindra Logistics. Mumbai, India. 500+ connections..."
    """
    link = item.get("link", "")
    if "/in/" not in link:
        return None

    linkedin_url = link.split("?")[0].rstrip("/")
    title_raw = item.get("title", "")
    snippet = item.get("snippet", "")

    # Strip " | LinkedIn" suffix
    title = re.sub(r'\s*\|\s*LinkedIn.*$', '', title_raw, flags=re.IGNORECASE).strip()

    name, job_title, company = "", "", ""

    # "Name - Job Title at Company"
    dash = re.match(r'^(.+?)\s*[-–]\s*(.+)$', title)
    if dash:
        name = dash.group(1).strip()
        role_part = dash.group(2).strip()
        at = re.search(r'\bat\s+(.+)$', role_part, re.IGNORECASE)
        if at:
            job_title = role_part[: at.start()].strip()
            company = at.group(1).strip()
        else:
            job_title = role_part
    else:
        name = title

    if not name or len(name) < 2:
        return None
    if any(x in name.lower() for x in ["linkedin", "profile", "view", "see"]):
        return None

    # Location from snippet
    location = ""
    loc = re.search(
        r'([A-Z][a-zA-Z\s]+,\s*(?:[A-Z][a-z]+,\s*)?India)',
        snippet,
    )
    if loc:
        location = loc.group(1).strip()

    return {
        "name": name,
        "job_title": job_title or None,
        "company": company or None,
        "location": location or None,
        "linkedin_url": linkedin_url,
    }


# ── DB helpers ────────────────────────────────────────────────────────────────

def _upsert_company(db: Session, name: str, location: str = "") -> Optional[ProspectCompany]:
    name = name.strip()
    if not name:
        return None
    existing = db.query(ProspectCompany).filter(ProspectCompany.name.ilike(name)).first()
    if existing:
        return existing
    company = ProspectCompany(name=name, location=location or None, source="google_search")
    db.add(company)
    db.flush()
    return company


def _upsert_contact(db: Session, company_id: UUID, data: dict) -> Optional[ProspectContact]:
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


# ── Main entry ────────────────────────────────────────────────────────────────

def search_linkedin_via_google(
    keyword: str,
    location: str = "India",
    target_roles: list[str] | None = None,
    max_per_role: int = 5,
) -> dict:
    """
    Search LinkedIn profiles on Google for each target role.
    Each role = 1 Google CSE query (free tier: 100 queries/day).
    Returns a summary dict compatible with the linkedin-scrape endpoint.
    """
    roles = target_roles or ["Manager", "Director", "CEO", "Operations", "Procurement"]

    result: dict = {
        "status": "ok",
        "companies_found": 0,
        "contacts_found": 0,
        "contacts": [],
        "errors": [],
    }

    if not settings.GOOGLE_CSE_ID:
        result["status"] = "config_missing"
        result["errors"].append(
            "GOOGLE_CSE_ID not set. "
            "Create a Custom Search Engine at https://programmablesearchengine.google.com/ "
            "and add GOOGLE_CSE_ID=<cx> to .env.local, then restart backend."
        )
        return result

    db: Session = SessionLocal()
    seen_urls: set[str] = set()
    seen_company_ids: set = set()

    try:
        for role in roles:
            query = f'site:linkedin.com/in/ "{role}" "{keyword}" "{location}"'
            logger.info(f"[GOOG LI] Query: {query}")

            items = _google_search(query, num=max_per_role)
            for item in items:
                profile = _parse_profile(item)
                if not profile or profile["linkedin_url"] in seen_urls:
                    continue
                seen_urls.add(profile["linkedin_url"])

                company_name = profile.get("company") or f"{keyword.title()} Company"
                company = _upsert_company(db, company_name, location=profile.get("location") or location)
                if not company:
                    continue

                if company.id not in seen_company_ids:
                    seen_company_ids.add(company.id)
                    result["companies_found"] += 1

                contact = _upsert_contact(db, company.id, profile)
                if contact:
                    result["contacts_found"] += 1
                    result["contacts"].append({
                        "name": profile["name"],
                        "job_title": profile.get("job_title"),
                        "company": company_name,
                        "location": profile.get("location"),
                        "linkedin_url": profile["linkedin_url"],
                    })

        db.commit()
        logger.info(
            f"[GOOG LI] Done — companies={result['companies_found']} contacts={result['contacts_found']}"
        )

        try:
            from app.services.ai_lead_scorer import batch_score_companies
            batch_score_companies(db)
        except Exception as e:
            logger.warning(f"[GOOG LI] Scoring skipped: {e}")

    except Exception as e:
        db.rollback()
        logger.error(f"[GOOG LI] Fatal: {e}", exc_info=True)
        result["status"] = "error"
        result["errors"].append(str(e))
    finally:
        db.close()

    return result


# ── Auto-search config (mirrors linkedin_scraper_service DEFAULT_AUTO_SEARCHES) ─

DEFAULT_GOOGLE_SEARCHES = [
    {"keyword": "manufacturing",         "location": "India", "roles": ["Plant Manager", "Operations Head", "Procurement Manager", "CEO"],      "max_per_role": 5},
    {"keyword": "industrial automation", "location": "India", "roles": ["Automation Engineer", "Plant Head", "Technical Director"],             "max_per_role": 4},
    {"keyword": "logistics",             "location": "India", "roles": ["Operations Manager", "Supply Chain Head", "Logistics Director"],       "max_per_role": 4},
    {"keyword": "oil gas energy",        "location": "India", "roles": ["Plant Manager", "Operations Director", "Instrumentation Engineer"],    "max_per_role": 4},
    {"keyword": "pharma",                "location": "India", "roles": ["Production Manager", "Plant Head", "Quality Director"],               "max_per_role": 4},
]


def run_auto_google_search(searches: list[dict] | None = None) -> dict:
    """Called by gmail_poller every 6 hours."""
    searches = searches or DEFAULT_GOOGLE_SEARCHES
    totals = {"contacts_found": 0, "companies_found": 0, "errors": []}
    for s in searches:
        r = search_linkedin_via_google(
            keyword=s.get("keyword", ""),
            location=s.get("location", "India"),
            target_roles=s.get("roles"),
            max_per_role=s.get("max_per_role", 5),
        )
        totals["contacts_found"] += r.get("contacts_found", 0)
        totals["companies_found"] += r.get("companies_found", 0)
        totals["errors"].extend(r.get("errors", []))
    return totals
