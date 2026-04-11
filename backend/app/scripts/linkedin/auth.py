import asyncio
import sys
from pathlib import Path
from linkedin_scraper import BrowserManager, login_with_credentials, wait_for_manual_login
from app.core.config import settings

backend_dir = str(Path(__file__).resolve().parents[3])
sys.path.append(backend_dir)

async def auto_login():
    print("🤖 Starting LinkedIn Authentication...")
    
    if not settings.LINKEDIN_EMAIL or not settings.LINKEDIN_PASSWORD:
        print("❌ Error: Missing credentials in .env.local!")
        return

    # 🛡️ CHANGE: headless=False so YOU can see the CAPTCHA
    async with BrowserManager(headless=False) as browser:
        try:
            print("🌐 Navigating to login...")
            await browser.page.goto("https://www.linkedin.com/login")
            
            print("⌨️ Entering credentials...")
            await login_with_credentials(
                browser.page,
                settings.LINKEDIN_EMAIL,
                settings.LINKEDIN_PASSWORD
            )
            
            # 🛡️ THE FALLBACK: If LinkedIn shows a puzzle or 'Join' screen
            if "checkpoint" in browser.page.url or "login" in browser.page.url:
                print("\n⚠️ CAPTCHA DETECTED! Please solve it in the browser window...")
                # This waits up to 5 mins for you to solve it manually
                await wait_for_manual_login(browser.page, timeout=300)
            
            # Save the session
            session_path = Path(backend_dir) / "session.json"
            await browser.save_session(str(session_path))
            print(f"✅ Success! Session saved to {session_path}")
            
        except Exception as e:
            print(f"❌ Login failed: {e}")

if __name__ == "__main__":
    asyncio.run(auto_login())