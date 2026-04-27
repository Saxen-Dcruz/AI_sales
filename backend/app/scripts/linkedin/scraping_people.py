"""
LinkedIn people scraper — finds decision-makers at scraped companies.

Usage:
  # Inside Docker (headless):
  docker compose exec backend python app/scripts/linkedin/scraping_people.py --headless

  # On your machine (browser window):
  python app/scripts/linkedin/scraping_people.py

  # Limit to N leads per company:
  python app/scripts/linkedin/scraping_people.py --headless --limit-per-company 5

  # Target a specific company by name:
  python app/scripts/linkedin/scraping_people.py --headless --company "RDL Technologies"
"""
import argparse
import asyncio
import random
import sys
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)
session_file = str(Path(backend_dir) / "session.json")

from app.database.core import SessionLocal
from app.models.leads import Lead
from app.models.company import Company
from app.scripts.linkedin.sourcing import find_decision_makers, TARGET_ROLES

TARGET_TITLES = TARGET_ROLES  # uses the comprehensive list from sourcing.py


async def run_people_scraper(headless: bool, limit_per_company: int, company_filter: str):
    from linkedin_scraper import BrowserManager, PersonScraper

    print(f"🚀 Starting people scraper | headless={headless} | limit_per_company={limit_per_company or 'unlimited'}")

    with SessionLocal() as db:
        q = db.query(Company)
        if company_filter:
            q = q.filter(Company.name.ilike(f"%{company_filter}%"))
        companies = q.all()

    if not companies:
        print(f"❌ No companies found{f' matching {company_filter!r}' if company_filter else ''}.")
        print("   Run scrape_companies.py first to populate the companies table.")
        return

    print(f"  Found {len(companies)} compan{'y' if len(companies) == 1 else 'ies'} to process")

    async with BrowserManager(headless=headless) as browser:
        if not headless:
            # Try loading a saved session
            session_path = Path(session_file)
            if session_path.exists():
                print(f"  Loading session from {session_file}...")
                await browser.load_session(session_file)
            else:
                print("  No saved session. Run auth.py first or log in manually.")

        scraper = PersonScraper(browser.page)
        total_saved = 0

        for company in companies:
            print(f"\n🏢 {company.name}")
            company_saved = 0

            for title in TARGET_TITLES:
                if limit_per_company and company_saved >= limit_per_company:
                    break

                people_urls = find_decision_makers(
                    company.name,
                    max_results=30,
                    roles=[title],
                    delay_min=3.0,
                    delay_max=6.0,
                )

                for url in people_urls:
                    if limit_per_company and company_saved >= limit_per_company:
                        break

                    with SessionLocal() as db:
                        if db.query(Lead).filter(Lead.linkedin_url == url).first():
                            print(f"  ⏭️  Already in DB: {url}")
                            continue

                    print(f"  ⚡ Scraping: {url}")
                    try:
                        person = await scraper.scrape(url)

                        current_job = "Unknown"
                        if hasattr(person, "experiences") and person.experiences:
                            current_job = person.experiences[0].title

                        with SessionLocal() as db:
                            lead = Lead(
                                company_id=company.id,
                                name=getattr(person, "name", "Unknown"),
                                linkedin_url=url,
                                headline=getattr(person, "headline", None),
                                location=getattr(person, "location", None),
                                current_role=current_job,
                                about=getattr(person, "about", ""),
                                status="Uncontacted",
                                interest_level="Cold",
                            )
                            db.add(lead)
                            db.commit()
                            print(f"  ✅ Saved: {lead.name} — {current_job}")
                            company_saved += 1
                            total_saved += 1

                    except Exception as e:
                        print(f"  ❌ Error: {e}")

                    sleep_time = random.uniform(15, 30)
                    print(f"  💤 Sleeping {round(sleep_time)}s...")
                    await asyncio.sleep(sleep_time)

        print(f"\n🎉 Done. Total leads saved: {total_saved}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn people scraper")
    parser.add_argument("--headless", action="store_true",
                        help="Run headless (no browser window — works inside Docker)")
    parser.add_argument("--limit-per-company", type=int, default=0,
                        help="Max leads to save per company (0 = unlimited)")
    parser.add_argument("--company", type=str, default="",
                        help="Filter to companies matching this name")
    args = parser.parse_args()

    asyncio.run(run_people_scraper(
        headless=args.headless,
        limit_per_company=args.limit_per_company,
        company_filter=args.company,
    ))
