import asyncio
import sys
from pathlib import Path

# Go up exactly 4 folders to reach the 'backend' directory and add it to the path
backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)

from linkedin_scraper import BrowserManager, login_with_credentials
from app.core.config import settings

async def auto_login():
    print("🤖 Attempting fully automated invisible login...")
    
    # 1. Check if the credentials successfully loaded from config.py
    if not settings.LINKEDIN_EMAIL or not settings.LINKEDIN_PASSWORD:
        print("❌ Error: Missing LinkedIn credentials in .env.local!")
        return

    # 2. headless=True means the browser runs completely hidden!
    async with BrowserManager(headless=True) as browser:
        try:
            # 3. Automatically type the credentials (passing positionally to avoid library typos)
            await login_with_credentials(
                browser.page,
                settings.LINKEDIN_EMAIL,
                settings.LINKEDIN_PASSWORD
            )
            
            # 4. Save the session cookies
            session_path = Path(backend_dir) / "session.json"
            await browser.save_session(str(session_path))
            print(f"✅ Success! Automated login complete and session saved to {session_path}")
            
        except Exception as e:
            print(f"❌ Automated login failed. Error: {e}")
            print("\n⚠️ THE LINKEDIN CAPTCHA TRAP ⚠️")
            print("If this failed, LinkedIn detected a bot and threw a CAPTCHA.")
            print("To fix this: Change 'headless=True' to 'headless=False' on line 21, run it once manually to solve the puzzle, and then change it back.")

if __name__ == "__main__":
    asyncio.run(auto_login())