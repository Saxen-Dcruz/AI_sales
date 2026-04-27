"""
Live discovery test — no browser required.

Tests the full URL discovery pipeline (DDGS + Google fallback)
with a small subset and prints results. Use this to confirm the
search backends are working before running the full scrape.

Usage:
  docker compose exec backend python app/scripts/linkedin/test_discovery.py
  docker compose exec backend python app/scripts/linkedin/test_discovery.py --cities "Pune,Mumbai" --industries "pharma"
  docker compose exec backend python app/scripts/linkedin/test_discovery.py --backend ddgs
  docker compose exec backend python app/scripts/linkedin/test_discovery.py --backend google
"""
import argparse
import sys
import time
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)


DEFAULT_CITIES     = ["Pune", "Mumbai", "Ahmedabad", "Chennai"]
DEFAULT_INDUSTRIES = ["pharmaceutical manufacturing", "automotive manufacturing",
                      "textile manufacturing", "chemical manufacturing"]


def test_ddgs(cities, industries, max_results=20):
    from app.scripts.linkedin.sourcing import _ddgs_search, QUERY_VARIANTS
    print("\n── DDGS Backend ──────────────────────────────────────────────────")
    total = 0
    for city in cities:
        for industry in industries:
            for variant in QUERY_VARIANTS[:2]:  # 2 variants to keep it quick
                query = variant.format(industry=industry, city=city)
                print(f"  Query: {query[:80]}")
                t0 = time.perf_counter()
                urls = _ddgs_search(query, max_results=max_results)
                elapsed = round(time.perf_counter() - t0, 1)
                print(f"  → {len(urls)} URLs in {elapsed}s")
                for u in urls[:3]:
                    print(f"    {u}")
                total += len(urls)
                time.sleep(3)
    print(f"\n  DDGS total: {total} URLs from {len(cities) * len(industries) * 2} queries")
    return total


def test_google(cities, industries, max_results=10):
    from app.scripts.linkedin.sourcing import _google_search, QUERY_VARIANTS
    print("\n── Google Backend ────────────────────────────────────────────────")
    total = 0
    for city in cities[:2]:  # smaller batch — Google is slower
        for industry in industries[:2]:
            query = QUERY_VARIANTS[0].format(industry=industry, city=city)
            print(f"  Query: {query[:80]}")
            t0 = time.perf_counter()
            urls = _google_search(query, max_results=max_results)
            elapsed = round(time.perf_counter() - t0, 1)
            print(f"  → {len(urls)} URLs in {elapsed}s")
            for u in urls[:3]:
                print(f"    {u}")
            total += len(urls)
            time.sleep(5)
    print(f"\n  Google total: {total} URLs from {2 * 2} queries")
    return total


def test_full_pipeline(cities, industries, max_results=20):
    from app.scripts.linkedin.sourcing import find_companies_at_scale
    print("\n── Full Pipeline (DDGS + Google fallback) ────────────────────────")
    t0 = time.perf_counter()
    urls = find_companies_at_scale(
        city_batch=cities,
        industry_batch=industries,
        max_results_per_query=max_results,
        delay_min=2.0,
        delay_max=4.0,
    )
    elapsed = round(time.perf_counter() - t0, 1)
    print(f"\n  ✅ {len(urls)} unique company URLs in {elapsed}s")
    print(f"  Sample (first 10):")
    for u in urls[:10]:
        print(f"    {u}")

    # Check if any are already in DB
    try:
        from app.database.core import SessionLocal
        from app.models.company import Company
        with SessionLocal() as db:
            existing_count = db.query(Company).count()
            print(f"\n  DB: {existing_count} companies already scraped")
    except Exception:
        pass

    return urls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test LinkedIn URL discovery (no browser needed)")
    parser.add_argument("--cities", type=str, default="",
                        help=f"Comma-separated cities (default: {', '.join(DEFAULT_CITIES)})")
    parser.add_argument("--industries", type=str, default="",
                        help="Comma-separated industries (default: pharma, auto, textile, chemical)")
    parser.add_argument("--backend", choices=["ddgs", "google", "all"], default="all",
                        help="Which search backend to test (default: all)")
    parser.add_argument("--max-results", type=int, default=20,
                        help="Max results per query (default: 20)")
    args = parser.parse_args()

    cities     = [c.strip() for c in args.cities.split(",")    if c.strip()] or DEFAULT_CITIES
    industries = [i.strip() for i in args.industries.split(",") if i.strip()] or DEFAULT_INDUSTRIES

    print(f"🔍 LinkedIn Discovery Test")
    print(f"   Cities:     {cities}")
    print(f"   Industries: {industries}")
    print(f"   Backend:    {args.backend}")
    print(f"   Max results: {args.max_results} per query")

    if args.backend == "ddgs":
        test_ddgs(cities, industries, args.max_results)
    elif args.backend == "google":
        test_google(cities, industries, args.max_results)
    else:
        # Full pipeline — DDGS primary + Google fallback
        urls = test_full_pipeline(cities, industries, args.max_results)
        print(f"\n✅ Discovery test complete — {len(urls)} URLs ready for scraping.")
        print("   Next step: Run scrape_companies.py --headless to pull company data from LinkedIn.")
