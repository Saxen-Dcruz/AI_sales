import asyncio
import sys
from pathlib import Path
from linkedin_scraper import BrowserManager, CompanyScraper

# 1. Path routing trick so it knows exactly where the session.json is
backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)
session_file = str(Path(backend_dir) / "session.json")

async def run_test():
    # Bypassing Google and feeding it guaranteed URLs
    urls = [
        "https://www.linkedin.com/company/ford-motor-company/",
        "https://www.linkedin.com/company/3m/"
    ]

    print("🤖 Booting up the scraper using your saved session...")
    
    # headless=True so it stays completely invisible
    async with BrowserManager(headless=True) as browser:
        # Load the golden ticket!
        await browser.load_session(session_file)
        scraper = CompanyScraper(browser.page)
        
        for url in urls:
            print(f"\n⚡ Scraping {url}...")
            try:
                # This is where the magic happens
                data = await scraper.scrape(url)
                
                print(f"✅ SUCCESS! Extracted Data:")
                print(f"  🏢 Name: {data.name}")
                print(f"  🏭 Industry: {data.industry}")
                print(f"  👥 Size: {data.company_size}")
                print(f"  📍 Headquarters: {data.headquarters}")
                
            except Exception as e:
                print(f"❌ Failed to scrape {url}. Error: {e}")
            
            # Wait 5 seconds before the next one so LinkedIn doesn't get mad
            print("⏳ Waiting 5 seconds...")
            await asyncio.sleep(5)
            
    print("\n🎉 Test Complete!")

if __name__ == "__main__":
    asyncio.run(run_test())