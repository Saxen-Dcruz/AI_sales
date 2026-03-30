import asyncio
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from linkedin_scraper import BrowserManager, CompanyScraper

# 1. Path routing trick
backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)
session_file = str(Path(backend_dir) / "session.json")

# 2. Import Database modules
from app.database.core import SessionLocal, engine 
from app.models.leads import Base, Company
from app.scripts.linkedin.sourcing import find_companies_at_scale

async def safe_extract(page, selector):
    """Aggressively extracts text straight from the raw HTML DOM."""
    try:
        locator = page.locator(selector)
        
        # 🛡️ THE FIX: Force the robot to wait up to 2 seconds for LinkedIn to render the box
        await locator.first.wait_for(state="attached", timeout=2000)
        
        if await locator.count() > 0:
            # text_content() rips the raw data out even if LinkedIn tries to hide it visually!
            text = await locator.first.text_content()
            return " ".join(text.split()).strip()
    except Exception:
        pass
    
    return "Unknown"


async def run_company_scraper():
    print("🔍 Searching dynamically for Manufacturing companies...")
    
    # Run the new City Matrix search
    company_urls = find_companies_at_scale()

    if not company_urls:
        print("❌ No URLs found. Wait 15 mins for rate limits to clear.")
        return

    db: Session = SessionLocal()
    
    # 🚀 THE BULK FILTER 🚀
    print("\n🗄️ Checking database for existing companies in bulk...")
    
    # Ask Postgres for ALL URLs it currently knows about, all at once
    existing_records = db.query(Company.linkedin_url).all()
    # Convert them to a super-fast Python Set
    existing_urls = {record[0] for record in existing_records if record[0]}
    
    # Filter the list: Only keep URLs that are NOT in the database
    new_urls = [url for url in company_urls if url.split('?')[0].replace('/about', '').rstrip('/') not in existing_urls]
    
    print(f"📊 Search yielded {len(company_urls)} URLs. {len(existing_urls)} already in DB.")
    print(f"✨ Found {len(new_urls)} BRAND NEW companies to scrape!")

    if not new_urls:
        print("🛑 All found companies are already in the database. Exiting.")
        db.close()
        return
    
    async with BrowserManager(headless=True) as browser:
        print("🤖 Loading LinkedIn session...")
        await browser.load_session(session_file)
        
        # 🚀 THE SPEED HACK (Restored) 🚀
        browser.page.set_default_timeout(5000) 
        
        scraper = CompanyScraper(browser.page)
        
        # 🛡️ FIX 1: Iterate over the filtered 'new_urls' list, NOT the raw 'company_urls'!
        for raw_url in new_urls:
            
            # URL CLEANING & ABOUT TAB FORCING
            clean_url = raw_url.split('?')[0]
            if clean_url.endswith('/'):
                clean_url = clean_url[:-1]
            if not clean_url.endswith('/about'):
                clean_url = f"{clean_url}/about"

            print(f"\n⚡ Scraping {clean_url}...")
            
            # Sleep moved here so we don't sleep after an error or at the very end unnecessarily
            await asyncio.sleep(8) 
            
            try:
                # 1. Let the library do its default scrape
                data = await scraper.scrape(clean_url)
                
                # 🚀 THE HUMAN SCROLL HACK 🚀
                # Scroll down in chunks so the lazy-loader actually triggers!
                for i in range(1, 4):
                    await browser.page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/3})")
                    await asyncio.sleep(1) # Wait 1 sec per scroll
                
                # 2. THE BROADER SELECTOR
                pw_website = await safe_extract(browser.page, '[data-test-id="about-us__website"] dd')
                
                if pw_website != 'Unknown':
                    # Grab just the URL to avoid screen-reader text
                    pw_website = pw_website.split(" ")[0]

                pw_hq = await safe_extract(browser.page, '[data-test-id="about-us__headquarters"] dd')
                pw_size = await safe_extract(browser.page, '[data-test-id="about-us__size"] dd')
                pw_industry = await safe_extract(browser.page, '[data-test-id="about-us__industry"] dd')

                # 3. 🛡️ THE BULLETPROOF HYBRID MERGE 🛡️
                lib_website = getattr(data, 'website', None)
                company_website = pw_website if pw_website not in ['Unknown', None] else (lib_website if lib_website else "Unknown")
                
                lib_hq = getattr(data, 'headquarters', None)
                company_hq = pw_hq if pw_hq not in ['Unknown', None] else (lib_hq if lib_hq else "Unknown")
                
                lib_size = getattr(data, 'company_size', None)
                company_size = pw_size if pw_size not in ['Unknown', None] else (lib_size if lib_size else "Unknown")

                lib_industry = getattr(data, 'industry', None)
                company_industry = pw_industry if pw_industry not in ['Unknown', None] else (lib_industry if lib_industry else "Unknown")

                company_name = getattr(data, 'name', 'Unknown')
                company_about = getattr(data, 'about', getattr(data, 'description', 'Unknown'))

                # 4. Save to Database
                new_company = Company(
                    name=company_name,
                    linkedin_url=clean_url.replace('/about', ''), 
                    website=company_website,  
                    industry=company_industry,
                    company_size=company_size,
                    headquarters=company_hq,
                    about=company_about
                )
                
                db.add(new_company)
                db.commit()
                print(f"✅ SAVED TO DATABASE: {new_company.name}")
                print(f"   🔗 Website: {new_company.website}")
                
            except Exception as e:
                print(f"❌ Error scraping {clean_url}: {e}")
                db.rollback()
                
    db.close()

if __name__ == "__main__":
    asyncio.run(run_company_scraper())