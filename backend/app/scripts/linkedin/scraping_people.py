import asyncio
import sys
import time
from pathlib import Path
from sqlalchemy.orm import Session
from linkedin_scraper import BrowserManager, PersonScraper
import random

# 1. Path routing trick
backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)
session_file = str(Path(backend_dir) / "session.json")

# 2. Import Database modules
from app.database.core import SessionLocal, engine
from app.models.leads import Base, Company, Lead
from app.scripts.linkedin.sourcing import find_decision_makers

# 3. 🚨 MAGIC FIX: Ensure tables exist!
print("🏗️ Ensuring database tables exist...")
Base.metadata.create_all(bind=engine)

TARGET_TITLES = [
    "Plant Manager", 
    "Director of Manufacturing", 
    "VP of Operations", 
    "Chief Operating Officer",
    "Supply Chain Director",
    "Production Manager",
    "Quality Assurance Director",
    "Operations Manager"
]

async def run_people_scraper():
    db: Session = SessionLocal()
    
    companies = db.query(Company).all()
    if not companies:
        print("❌ No companies found in the DB. Run scrape_companies.py first!")
        return
    
    async with BrowserManager(headless=True) as browser:
        print("🤖 Loading LinkedIn session...")
        await browser.load_session(session_file)
        scraper = PersonScraper(browser.page)
        
        for company in companies:
            print(f"\n========================================")
            print(f"🏢 Hunting for executives at {company.name}")
            print(f"========================================")
            
            for title in TARGET_TITLES:
                # 🦆 Search DuckDuckGo
                people_urls = find_decision_makers(company.name, job_title=title, num_results=30)
                
                # 🛑 CRITICAL: Pause for 5 seconds between searches so DuckDuckGo doesn't ban us!
                time.sleep(5)
                
                for url in people_urls:
                    if db.query(Lead).filter(Lead.linkedin_url == url).first():
                        print(f"⏭️ Skipping {url} - Already in database.")
                        continue
                        
                    print(f"⚡ Scraping Person: {url}")
                    try:
                        person = await scraper.scrape(url)
                        
                        # 🛡️ BULLETPROOF EXTRACTION 🛡️
                        # Safely grab the current job title without crashing if their experience list is empty
                        current_job = "Unknown"
                        if hasattr(person, 'experiences') and person.experiences:
                            current_job = person.experiences[0].title

                        # Safely insert the new Lead matching your updated database model
                        new_lead = Lead(
                            company_id=company.id,
                            name=getattr(person, 'name', 'Unknown'),
                            linkedin_url=url, # Use the URL we fed it
                            headline=getattr(person, 'headline', 'Unknown'),
                            location=getattr(person, 'location', 'Unknown'),
                            current_role=current_job,
                            about=getattr(person, 'about', ''),
                            # Email and phone default to None based on your models.py
                            email=None, 
                            phone=None,
                            status="new"
                        )
                        db.add(new_lead)
                        db.commit()
                        print(f"✅ Saved Lead: {new_lead.name} ({current_job})")
                        
                    except Exception as e:
                        print(f"❌ Error scraping {url}: {e}")
                        db.rollback()
                    
                    # 🛡️ THE HUMAN RANDOMIZER 🛡️
                    # Wait between 15 and 35 seconds randomly so you don't look like a bot
                    sleep_time = random.uniform(15.5, 35.5)
                    print(f"💤 Sleeping for {round(sleep_time, 1)} seconds to trick LinkedIn...")
                    await asyncio.sleep(sleep_time)
                
    db.close()

if __name__ == "__main__":
    asyncio.run(run_people_scraper())