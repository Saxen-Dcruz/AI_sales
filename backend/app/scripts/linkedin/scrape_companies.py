"""
LinkedIn company scraper.

Usage:
  # Inside Docker (headless — no display needed):
  docker compose exec backend python app/scripts/linkedin/scrape_companies.py --headless

  # On your machine (browser window opens — you can solve CAPTCHAs):
  python app/scripts/linkedin/scrape_companies.py

  # Limit to N companies for a quick test:
  python app/scripts/linkedin/scrape_companies.py --headless --limit 10

  # Use a specific city/industry for targeted discovery:
  python app/scripts/linkedin/scrape_companies.py --headless --cities "Pune,Mumbai" --industries "pharma"
"""
import argparse
import asyncio
import sys
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)

user_data_dir = Path(backend_dir) / "linkedin_profile_context"
user_data_dir.mkdir(exist_ok=True)

from app.database.core import SessionLocal
from app.models.company import Company
from app.scripts.linkedin.sourcing import find_companies_at_scale


async def run_company_scraper(headless: bool, limit: int, cities: list[str], industries: list[str]):
    from playwright.async_api import async_playwright
    from linkedin_scraper import CompanyScraper

    print(f"🚀 Starting company scraper | headless={headless} | limit={limit}")

    # 1. Discover URLs
    with SessionLocal() as db:
        existing = {r[0].split("?")[0].rstrip("/").replace("/about", "")
                    for r in db.query(Company.linkedin_url).all() if r[0]}

    print(f"  Existing in DB: {len(existing)} companies — will skip these")

    found_urls = find_companies_at_scale(
        city_batch=cities or None,
        industry_batch=industries or None,
        max_results_per_query=50 if (cities or industries) else 100,
        delay_min=2.0,
        delay_max=5.0,
        existing_urls=existing,
    )

    if not found_urls:
        print("❌ No new company URLs found. Try different cities/industries.")
        return

    if limit:
        found_urls = found_urls[:limit]
        print(f"  Limiting to {limit} URLs for this run")

    print(f"\n🌐 Scraping {len(found_urls)} company profiles...")

    async with async_playwright() as p:
        if headless:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"],
            )
        else:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

        page = context.pages[0] if context.pages else await context.new_page()
        scraper = CompanyScraper(page)

        saved = 0
        skipped = 0

        for raw_url in found_urls:
            clean_url = raw_url.split("?")[0].rstrip("/")
            if not clean_url.endswith("/about"):
                clean_url = f"{clean_url}/about"

            print(f"  ⚡ {clean_url}")

            try:
                await page.goto(clean_url, wait_until="commit", timeout=20_000)

                # Handle login redirect
                if "checkpoint" in page.url or "login" in page.url:
                    if headless:
                        print("  🔒 Redirected to login — session may have expired. Run auth.py first.")
                        break
                    else:
                        print("  🚨 Checkpoint! Solve it in the browser window...")
                        while "checkpoint" in page.url or "login" in page.url:
                            await asyncio.sleep(2)

                data = await scraper.scrape(clean_url)

                if not data.name or data.name in ("Welcome back", "LinkedIn", "Sign Up", ""):
                    print(f"  ⏭️  Not logged in or no data — skipping")
                    skipped += 1
                    continue

                with SessionLocal() as db:
                    if db.query(Company).filter(Company.linkedin_url == clean_url.replace("/about", "")).first():
                        skipped += 1
                        continue
                    new_co = Company(
                        name=data.name,
                        linkedin_url=clean_url.replace("/about", ""),
                        website=getattr(data, "website", None),
                        industry=getattr(data, "industry", None),
                        company_size=getattr(data, "company_size", "Unknown"),
                        headquarters=getattr(data, "headquarters", None),
                        about=getattr(data, "about", None),
                    )
                    db.add(new_co)
                    db.commit()
                    print(f"  ✅ Saved: {new_co.name}")
                    saved += 1

            except Exception as e:
                print(f"  ❌ Error: {e}")

            await asyncio.sleep(2)

        await context.close()

    print(f"\n🎉 Done. Saved={saved} | Skipped={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn company scraper")
    parser.add_argument("--headless", action="store_true",
                        help="Run in headless mode (no browser window — works inside Docker)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max companies to scrape (0 = unlimited)")
    parser.add_argument("--cities", type=str, default="",
                        help="Comma-separated city names (default: all 200+ cities)")
    parser.add_argument("--industries", type=str, default="",
                        help="Comma-separated industry names (default: all 80+ industries)")
    args = parser.parse_args()

    city_list     = [c.strip() for c in args.cities.split(",")    if c.strip()] or None
    industry_list = [i.strip() for i in args.industries.split(",") if i.strip()] or None

    asyncio.run(run_company_scraper(
        headless=args.headless,
        limit=args.limit,
        cities=city_list,
        industries=industry_list,
    ))
