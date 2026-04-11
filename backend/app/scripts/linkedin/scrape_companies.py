import asyncio
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright # Import Playwright directly

# 1. Path routing
backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)
user_data_dir = Path(backend_dir) / "linkedin_profile_context"
user_data_dir.mkdir(exist_ok=True) # Ensure folder exists

from app.database.core import SessionLocal
from app.models.company import Company
from app.scripts.linkedin.sourcing import find_companies_at_scale
from linkedin_scraper import CompanyScraper

async def run_company_scraper():
    print("🚀 Starting High-Speed Persistent Scraper...")
    company_urls = find_companies_at_scale()
    if not company_urls: return

    db: Session = SessionLocal()
    
    # Filter Logic
    existing_records = db.query(Company.linkedin_url).all()
    existing_urls = {record[0].split('?')[0].rstrip('/') for record in existing_records if record[0]}
    new_urls = [url for url in company_urls if url.split('?')[0].replace('/about', '').rstrip('/') not in existing_urls]

    # 🛡️ Launching Playwright manually to use launch_persistent_context
    async with async_playwright() as p:
        # This acts like your real Chrome browser
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"] # Helps hide bot status
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        scraper = CompanyScraper(page)
        
        for raw_url in new_urls:
            clean_url = raw_url.split('?')[0].rstrip('/')
            if not clean_url.endswith('/about'):
                clean_url = f"{clean_url}/about"

            print(f"⚡ Scraping {clean_url}...")
            
            try:
                await page.goto(clean_url, wait_until="commit")

                # Manual solve check
                if "checkpoint" in page.url or "login" in page.url:
                    print("🚨 Checkpoint! Solve it in the browser window...")
                    while "checkpoint" in page.url or "login" in page.url:
                        await asyncio.sleep(2)
                
                data = await scraper.scrape(clean_url)
                
                if data.name in ["Welcome back", "LinkedIn", "Sign Up"]:
                    continue

                new_company = Company(
                    name=data.name,
                    linkedin_url=clean_url.replace('/about', ''), 
                    website=getattr(data, 'website', "Unknown"),
                    industry=getattr(data, 'industry', "Unknown"),
                    company_size=getattr(data, 'company_size', "Unknown"),
                    headquarters=getattr(data, 'headquarters', "Unknown"),
                    about=getattr(data, 'about', "Unknown")
                )
                
                db.add(new_company)
                db.commit()
                print(f"✅ Saved: {new_company.name}")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                db.rollback()
                
        await context.close()
    db.close()

if __name__ == "__main__":
    asyncio.run(run_company_scraper())