"""
LinkedIn Lead Scraper — uses the linkedin_scraper package (Playwright-based)

Patterns taken from LinkdenScrapper project:
  - People search at /search/results/people/ with keyword+location+title filters
  - Card selectors: .search-results-container ul > li
  - Name: span[dir="ltr"]  |  URL: a[href*="/in/"]
  - Pagination via button[aria-label="Next"]
  - Human delays + random scrolls + user-agent rotation
  - Session loaded from linkedin_profile_context/ (persistent context)

Flow:
  1. Open LinkedIn with saved session
  2. Search people by keyword + location + title
  3. Extract leads from search result cards (name, title, location, URL)
  4. Optionally visit profile page for richer data via PersonScraper
  5. Infer company from headline / profile
  6. Upsert ProspectCompany + ProspectContact
  7. Run AI scoring batch

Auto-search:
  Called by gmail_poller on a configurable interval (default every 6 hours).
"""
import asyncio
import logging
import random
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.core import SessionLocal
from app.models.lead_gen import ProspectCompany, ProspectContact

logger = logging.getLogger("rdl_app_logger")

LINKEDIN_BASE  = "https://www.linkedin.com"
_BACKEND_ROOT  = Path(__file__).resolve().parents[2]
USER_DATA_DIR  = str(_BACKEND_ROOT / "linkedin_profile_context")
SESSION_FILE   = _BACKEND_ROOT / "linkedin_session.json"

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]

LI_AT_FILE = _BACKEND_ROOT / "linkedin_profile_context" / "li_at.txt"


# ── Browser helpers ───────────────────────────────────────────────────────────

async def _human_delay(min_s: float = 2.0, max_s: float = 5.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _random_scroll(page):
    scroll = random.randint(300, 700)
    await page.mouse.wheel(0, scroll)
    await asyncio.sleep(random.uniform(0.8, 1.5))


def _get_li_at() -> str:
    """
    Return the li_at session cookie value, preferring the manually pasted
    li_at.txt (from Settings UI) over the auto-saved session JSON.
    Using just li_at avoids browser-fingerprint rejection when the session
    was saved on one OS/browser and loaded in another (e.g. Windows → Docker).
    """
    import json as _json

    # 1. Manually pasted via Settings UI
    if LI_AT_FILE.exists():
        val = LI_AT_FILE.read_text(encoding="utf-8").strip()
        if val:
            logger.info("[LI SCRAPER] Using li_at from li_at.txt")
            return val

    # 2. Extract from linkedin_session.json saved by auth_setup.py
    if SESSION_FILE.exists():
        try:
            state = _json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            li_at = next(
                (c["value"] for c in state.get("cookies", []) if c.get("name") == "li_at"),
                None,
            )
            if li_at:
                logger.info("[LI SCRAPER] Using li_at extracted from linkedin_session.json")
                return li_at
        except Exception as e:
            logger.warning(f"[LI SCRAPER] Could not read linkedin_session.json: {e}")

    return ""


async def _get_context(playwright):
    """
    Launch headless browser and inject the li_at cookie into a fresh context.
    A fresh context (not loaded from storage_state) avoids LinkedIn fingerprint
    rejection when the session was created on a different OS/browser.
    """
    li_at = _get_li_at()

    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ],
    )
    context = await browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )

    if li_at:
        await context.add_cookies([{
            "name": "li_at",
            "value": li_at,
            "domain": ".linkedin.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        }])
        logger.info("[LI SCRAPER] li_at cookie injected into fresh context")
    else:
        logger.warning("[LI SCRAPER] No li_at available — browser will be unauthenticated")

    return browser, context


async def _check_session(context, page) -> bool:
    """Navigate to feed and verify login."""
    await page.goto(f"{LINKEDIN_BASE}/feed/", timeout=20_000, wait_until="domcontentloaded")
    await asyncio.sleep(2)
    return await _is_logged_in(page)


def _read_credentials() -> tuple[str, str]:
    """Read LINKEDIN_EMAIL + LINKEDIN_PASSWORD from .env.local."""
    env_file = _BACKEND_ROOT / ".env.local"
    email, password = "", ""
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LINKEDIN_EMAIL="):
                email = line.split("=", 1)[1].strip().strip('"\'')
            elif line.startswith("LINKEDIN_PASSWORD="):
                password = line.split("=", 1)[1].strip().strip('"\'')
    return email, password


async def _auto_relogin(context, page) -> bool:
    """
    Attempt headless re-login using saved credentials.
    If successful, saves new session to linkedin_session.json.
    Returns True if logged in, False if CAPTCHA/OTP needed (manual required).
    """
    import json as _json
    email, password = _read_credentials()
    if not email or not password:
        logger.warning("[LI SCRAPER] No credentials in .env.local — cannot auto re-login")
        return False

    logger.info(f"[LI SCRAPER] Session expired — attempting auto re-login as {email}")

    try:
        await page.goto(f"{LINKEDIN_BASE}/login", wait_until="domcontentloaded", timeout=20_000)
        await asyncio.sleep(2)

        await page.wait_for_selector("#username", timeout=8_000, state="visible")
        await page.fill("#username", email)
        await asyncio.sleep(0.4)
        await page.fill("#password", password)
        await asyncio.sleep(0.4)
        await page.click('button[type="submit"]')
        await asyncio.sleep(4)

        # Check result
        for _ in range(15):
            if await _is_logged_in(page):
                break
            await asyncio.sleep(1)

        if not await _is_logged_in(page):
            logger.warning("[LI SCRAPER] Auto re-login failed — CAPTCHA/OTP required. Run auth_setup.py manually.")
            return False

        # Save refreshed session (both full JSON and portable li_at)
        storage_state = await context.storage_state()
        SESSION_FILE.write_text(_json.dumps(storage_state, indent=2), encoding="utf-8")
        li_at_val = next(
            (c["value"] for c in storage_state.get("cookies", []) if c.get("name") == "li_at"),
            None,
        )
        if li_at_val:
            LI_AT_FILE.parent.mkdir(parents=True, exist_ok=True)
            LI_AT_FILE.write_text(li_at_val, encoding="utf-8")
        logger.info("[LI SCRAPER] Session auto-refreshed and saved.")
        return True

    except Exception as e:
        logger.warning(f"[LI SCRAPER] Auto re-login error: {e}")
        return False


async def _is_logged_in(page) -> bool:
    try:
        url = page.url
        if any(x in url for x in ["/login", "/authwall", "/checkpoint", "/challenge"]):
            return False
        # Check for nav elements that only appear when logged in
        old = await page.locator('.global-nav__primary-link, [data-control-name="nav.settings"]').count()
        new = await page.locator('nav a[href*="/feed"], nav a[href*="/mynetwork"]').count()
        auth_page = any(x in url for x in ["/feed", "/mynetwork", "/messaging", "/notifications"])
        return old > 0 or new > 0 or auth_page
    except Exception:
        return False


# ── People search ─────────────────────────────────────────────────────────────

def _build_people_search_url(keyword: str, location: str, title: str = "") -> str:
    """Build LinkedIn people search URL — matches JS buildSearchUrl() logic."""
    parts = []
    if keyword:
        parts.append(keyword)
    if title:
        parts.append(f'"{title}"')
    if location:
        parts.append(f'"{location}"')
    query = " ".join(parts)
    from urllib.parse import quote
    return f"{LINKEDIN_BASE}/search/results/people/?keywords={quote(query)}&origin=GLOBAL_SEARCH_HEADER"


def _clean_text(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()


async def _extract_card_data(card) -> dict:
    """
    Extract lead data from a single search result card.
    Matches JS extractLeadData() logic exactly.
    """
    data = {}

    try:
        # Profile URL — a[href*="/in/"]
        links = await card.locator('a[href*="/in/"]').all()
        if not links:
            return {}
        raw_href = await links[0].get_attribute("href") or ""
        profile_url = raw_href.split("?")[0].rstrip("/")
        if not profile_url or "/in/" not in profile_url:
            return {}
        data["linkedin_url"] = profile_url if profile_url.startswith("http") else LINKEDIN_BASE + profile_url

        # Name — span[dir="ltr"] first match (JS pattern)
        dir_spans = await card.locator('span[dir="ltr"]').all()
        name = ""
        if dir_spans:
            name = await dir_spans[0].inner_text()
        else:
            for link in links:
                txt = await link.inner_text()
                if txt and "Status is" not in txt:
                    name = txt
                    break
        # Clean "View XXX's profile" suffix
        import re
        name = re.sub(r"View.*", "", name, flags=re.IGNORECASE).strip()
        if not name or "Status is offline" in name:
            return {}
        data["name"] = _clean_text(name)

        # Job title + location from card inner text (JS heuristic)
        full_text = await card.inner_text()
        lines = [_clean_text(l) for l in full_text.split("\n") if _clean_text(l)]
        data_lines = [
            l for l in lines
            if l
            and not any(x in l for x in [
                "degree connection", "3rd+", "2nd", "1st",
                "Status is", "View", "Followers", "Shared connections",
            ])
            and l != data["name"]
        ]
        data["job_title"] = data_lines[0] if len(data_lines) > 0 else ""
        data["location"]  = data_lines[1] if len(data_lines) > 1 else ""

        # Connection degree
        if "1st degree" in full_text:
            data["connection_degree"] = "1st"
        elif "2nd degree" in full_text:
            data["connection_degree"] = "2nd"
        else:
            data["connection_degree"] = "3rd+"

    except Exception as e:
        logger.debug(f"[LI SCRAPER] Card extraction error: {e}")
        return {}

    return data


async def _search_people(page, keyword: str, location: str, title: str, limit: int) -> list[dict]:
    """
    Navigate to LinkedIn people search and paginate through results.
    Matches JS searchLeads() flow.
    """
    results = []
    search_url = _build_people_search_url(keyword, location, title)
    logger.info(f"[LI SCRAPER] People search: {search_url}")

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=25_000)
        await _human_delay(3, 5)
    except Exception as e:
        logger.error(f"[LI SCRAPER] Failed to navigate to search: {e}")
        return results

    # Debug: log current URL and take screenshot to diagnose blank results
    current_url = page.url
    logger.info(f"[LI SCRAPER] After navigation URL: {current_url}")
    try:
        shot_path = str(_BACKEND_ROOT / "linkedin_debug.png")
        await page.screenshot(path=shot_path, full_page=False)
        logger.info(f"[LI SCRAPER] Screenshot saved: {shot_path}")
    except Exception:
        pass

    if any(x in current_url for x in ["/login", "/authwall", "/checkpoint", "/challenge"]):
        logger.warning(f"[LI SCRAPER] Redirected to auth page: {current_url} — session invalid in headless mode")
        return results

    while len(results) < limit:
        await _random_scroll(page)

        # Cards: .search-results-container ul > li (JS selector)
        cards = await page.locator(".search-results-container ul > li").all()
        if not cards:
            # Fallback selector
            cards = await page.locator('[data-view-name="search-entity-result-universal-template"]').all()
        logger.info(f"[LI SCRAPER] Found {len(cards)} cards on page")

        for card in cards:
            if len(results) >= limit:
                break
            lead = await _extract_card_data(card)
            if lead.get("name") and lead.get("linkedin_url"):
                # Deduplicate
                if not any(r["linkedin_url"] == lead["linkedin_url"] for r in results):
                    results.append(lead)

        # Pagination — button[aria-label="Next"] (JS pattern)
        next_btn = page.locator('button[aria-label="Next"]')
        if await next_btn.count() > 0 and await next_btn.is_visible() and len(results) < limit:
            await next_btn.click()
            await _human_delay(3, 5)
        else:
            break

    logger.info(f"[LI SCRAPER] Extracted {len(results)} people")
    return results


# ── Company inference ─────────────────────────────────────────────────────────

def _infer_company_from_headline(headline: str) -> Optional[str]:
    """Extract company name from headline like 'Senior Manager at Tata Steel'."""
    if not headline:
        return None
    import re
    match = re.search(r'\bat\s+(.+?)(?:\s*[\|·,]|$)', headline, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


# ── DB helpers ────────────────────────────────────────────────────────────────

def _upsert_company(db: Session, name: str, industry: str = "", location: str = "") -> Optional[ProspectCompany]:
    name = name.strip()
    if not name:
        return None
    existing = db.query(ProspectCompany).filter(ProspectCompany.name.ilike(name)).first()
    if existing:
        return existing
    company = ProspectCompany(
        name=name,
        industry=industry or None,
        location=location or None,
        source="linkedin_scrape",
    )
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


def _get_or_create_unknown_company(db: Session, location: str) -> ProspectCompany:
    """Fallback company bucket for contacts whose company couldn't be inferred."""
    name = f"Unknown Company ({location or 'Unknown'})"
    return _upsert_company(db, name, location=location) or ProspectCompany(name=name)


# ── Main entry points ─────────────────────────────────────────────────────────

async def run_linkedin_scrape(
    keyword: str,
    location: str = "India",
    target_roles: list[str] | None = None,
    max_results: int = 20,
) -> dict:
    """
    Main async entry point for manual trigger (from API endpoint).
    Searches LinkedIn people by keyword + each target role.
    """
    from playwright.async_api import async_playwright

    target_roles = target_roles or ["Manager", "Director", "CEO", "Operations", "Procurement"]

    result = {
        "status": "ok",
        "companies_found": 0,
        "contacts_found": 0,
        "errors": [],
    }

    if not SESSION_FILE.exists():
        result["status"] = "auth_required"
        result["errors"].append("LinkedIn session not set up. Run: python app/scripts/linkedin/auth_setup.py")
        return result

    try:
        async with async_playwright() as pw:
            browser, context = await _get_context(pw)
            page = await context.new_page()

            if not await _check_session(context, page):
                if not await _auto_relogin(context, page):
                    msg = "LinkedIn session expired and auto re-login failed (CAPTCHA needed). Run auth_setup.py manually."
                    logger.warning(f"[LI SCRAPER] {msg}")
                    result["status"] = "auth_required"
                    result["errors"].append(msg)
                    await browser.close()
                    return result

            db: Session = SessionLocal()
            try:
                per_role = max(1, max_results // len(target_roles))

                for role in target_roles:
                    people = await _search_people(page, keyword, location, role, per_role)
                    await _human_delay(3, 6)

                    for person in people:
                        company_name = _infer_company_from_headline(person.get("job_title", ""))
                        if not company_name:
                            company_name = f"{keyword.title()} Company"
                        company = _upsert_company(db, company_name, location=person.get("location", ""))
                        if not company:
                            continue
                        result["companies_found"] += 1
                        contact = _upsert_contact(db, company.id, person)
                        if contact:
                            result["contacts_found"] += 1

                db.commit()
                logger.info(f"[LI SCRAPER] Done — contacts={result['contacts_found']}")

                try:
                    from app.services.ai_lead_scorer import batch_score_companies
                    batch_score_companies(db)
                except Exception as e:
                    logger.warning(f"[LI SCRAPER] Scoring skipped: {e}")

            finally:
                db.close()

            await browser.close()

    except Exception as e:
        logger.error(f"[LI SCRAPER] Fatal: {e}", exc_info=True)
        result["status"] = "error"
        result["errors"].append(str(e))

    return result


async def run_auto_search(searches: list[dict]) -> dict:
    """
    Auto-search entry point called by the poller.
    `searches` is a list of {keyword, location, roles, max_results}.

    Example:
      searches = [
        {"keyword": "manufacturing", "location": "India", "roles": ["Plant Manager", "Operations Head"], "max_results": 15},
        {"keyword": "logistics",     "location": "India", "roles": ["Manager", "Director"],                "max_results": 15},
      ]
    """
    from playwright.async_api import async_playwright

    totals = {"contacts_found": 0, "errors": []}

    try:
        async with async_playwright() as pw:
            browser, context = await _get_context(pw)
            page = await context.new_page()

            if not await _check_session(context, page):
                if not await _auto_relogin(context, page):
                    msg = "Auto-search skipped: session expired and auto re-login failed. Run auth_setup.py manually."
                    logger.warning(f"[LI AUTO] {msg}")
                    totals["errors"].append(msg)
                    await browser.close()
                    return totals

            db: Session = SessionLocal()
            try:
                for s in searches:
                    keyword  = s.get("keyword", "")
                    location = s.get("location", "India")
                    roles    = s.get("roles") or ["Manager", "Director", "CEO"]
                    limit    = s.get("max_results", 10)

                    logger.info(f"[LI AUTO] Searching '{keyword}' in '{location}'")

                    per_role = max(1, limit // len(roles))
                    for role in roles:
                        people = await _search_people(page, keyword, location, role, per_role)
                        await _human_delay(4, 8)

                        for person in people:
                            company_name = _infer_company_from_headline(person.get("job_title", "")) or f"{keyword.title()} Company"
                            company = _upsert_company(db, company_name, location=person.get("location", ""))
                            if not company:
                                continue
                            contact = _upsert_contact(db, company.id, person)
                            if contact:
                                totals["contacts_found"] += 1

                    await _human_delay(5, 10)

                db.commit()
                logger.info(f"[LI AUTO] Total contacts found: {totals['contacts_found']}")

                try:
                    from app.services.ai_lead_scorer import batch_score_companies
                    batch_score_companies(db)
                except Exception as e:
                    logger.warning(f"[LI AUTO] Scoring skipped: {e}")

            finally:
                db.close()

            await browser.close()

    except Exception as e:
        logger.error(f"[LI AUTO] Fatal: {e}", exc_info=True)
        totals["errors"].append(str(e))

    return totals


# ── Default auto-search config ────────────────────────────────────────────────
# Customize this to match RDL Technologies' ideal customer profile.

DEFAULT_AUTO_SEARCHES = [
    {"keyword": "manufacturing",        "location": "India", "roles": ["Plant Manager", "Operations Head", "Procurement Manager", "CEO"],         "max_results": 15},
    {"keyword": "industrial automation","location": "India", "roles": ["Automation Engineer", "Plant Head", "Technical Director"],                "max_results": 10},
    {"keyword": "logistics",            "location": "India", "roles": ["Operations Manager", "Supply Chain Head", "Logistics Director"],          "max_results": 10},
    {"keyword": "oil gas energy",       "location": "India", "roles": ["Plant Manager", "Operations Director", "Instrumentation Engineer"],       "max_results": 10},
    {"keyword": "pharma",               "location": "India", "roles": ["Production Manager", "Plant Head", "Quality Director"],                   "max_results": 10},
]
