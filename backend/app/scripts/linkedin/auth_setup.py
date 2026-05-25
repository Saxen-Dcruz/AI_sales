"""
LinkedIn Session Setup — run ONCE on your local Windows machine.

Reads LINKEDIN_EMAIL + LINKEDIN_PASSWORD from .env.local, auto-fills them,
warms up the browser first (visits Google/Wikipedia/GitHub so LinkedIn doesn't
flag it as a bot), then saves the full session to linkedin_session.json.

If LinkedIn shows a CAPTCHA or OTP, solve it manually in the browser window —
the script waits automatically.

Usage:
  cd d:\projects\AI_sales\backend
  python app/scripts/linkedin/auth_setup.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BACKEND_ROOT   = Path(__file__).resolve().parents[3]
SESSION_FILE   = BACKEND_ROOT / "linkedin_session.json"
LI_AT_FILE     = BACKEND_ROOT / "linkedin_profile_context" / "li_at.txt"
LINKEDIN_LOGIN = "https://www.linkedin.com/login"
WARM_UP_SITES  = ["https://www.google.com", "https://www.wikipedia.org", "https://www.github.com"]


def _read_credentials():
    email, password = "", ""
    env_file = BACKEND_ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("LINKEDIN_EMAIL="):
                email = line.split("=", 1)[1].strip().strip('"\'')
            elif line.startswith("LINKEDIN_PASSWORD="):
                password = line.split("=", 1)[1].strip().strip('"\'')
    return email, password


async def _warm_up(page):
    logger.info("Warming up browser (Google → Wikipedia → GitHub)...")
    for site in WARM_UP_SITES:
        try:
            await page.goto(site, wait_until="domcontentloaded", timeout=10_000)
            await asyncio.sleep(1.2)
        except Exception:
            pass
    logger.info("Warm-up done.")


async def _is_logged_in(page) -> bool:
    url = page.url
    if any(x in url for x in ["/login", "/authwall", "/checkpoint", "/challenge"]):
        return False
    nav = await page.locator(
        '.global-nav__primary-link, nav a[href*="/feed"], nav a[href*="/mynetwork"]'
    ).count()
    return nav > 0 or any(x in url for x in ["/feed", "/mynetwork", "/messaging"])


async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("playwright not installed. Run:  pip install playwright && playwright install chromium")
        sys.exit(1)

    email, password = _read_credentials()
    if not email:
        email = input("LinkedIn email: ").strip()
    if not password:
        import getpass
        password = getpass.getpass("LinkedIn password: ").strip()

    logger.info(f"Starting LinkedIn session setup for: {email}")
    logger.info(f"Session will be saved to: {SESSION_FILE}")

    async with async_playwright() as pw:
        # Try real installed Chrome first (avoids bot detection better than Playwright's Chromium)
        launch_kwargs = dict(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ],
        )
        try:
            browser = await pw.chromium.launch(channel="chrome", **launch_kwargs)
            logger.info("Using installed Google Chrome")
        except Exception:
            browser = await pw.chromium.launch(**launch_kwargs)
            logger.info("Using Playwright Chromium (Chrome not found)")

        context = await browser.new_context(
            viewport=None,  # use window size when maximized
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            no_viewport=True,
        )
        page = await context.new_page()

        # Warm up
        await _warm_up(page)

        # Navigate to login
        logger.info("Navigating to LinkedIn login...")
        await page.goto(LINKEDIN_LOGIN, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Auto-fill credentials
        try:
            await page.wait_for_selector("#username", timeout=10_000, state="visible")
            await page.fill("#username", email)
            await asyncio.sleep(0.5)
            await page.fill("#password", password)
            await asyncio.sleep(0.5)
            await page.click('button[type="submit"]')
            await asyncio.sleep(4)
            logger.info("Credentials submitted.")
        except Exception as e:
            logger.warning(f"Auto-fill error: {e} — please log in manually in the browser.")

        # Wait for login — poll until logged in or user confirms
        logger.info("Waiting for LinkedIn feed...")
        for _ in range(60):  # wait up to 60 seconds
            if await _is_logged_in(page):
                break
            await asyncio.sleep(1)
        else:
            # LinkedIn showed CAPTCHA / OTP / checkpoint
            logger.info("")
            logger.info(">> LinkedIn needs verification (CAPTCHA / OTP).")
            logger.info(">> Complete it in the browser window.")
            input(">> Press Enter here once you see the LinkedIn feed: ")

        if not await _is_logged_in(page):
            logger.error(f"Still not logged in. URL: {page.url}")
            logger.info("Navigate to your LinkedIn feed manually, then press Enter.")
            input()

        # Save full session (all cookies + storage state)
        storage_state = await context.storage_state()
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(json.dumps(storage_state, indent=2), encoding="utf-8")

        # Also extract and save li_at separately so Docker can use it portably
        li_at_val = next(
            (c["value"] for c in storage_state.get("cookies", []) if c.get("name") == "li_at"),
            None,
        )
        if li_at_val:
            LI_AT_FILE.parent.mkdir(parents=True, exist_ok=True)
            LI_AT_FILE.write_text(li_at_val, encoding="utf-8")
            logger.info(f"li_at cookie also saved to: {LI_AT_FILE}")

        logger.info("")
        logger.info(f"SUCCESS! Session saved to: {SESSION_FILE}")
        logger.info("The scraper will use this session automatically.")
        logger.info("You do not need to run this script again unless the session expires.")

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
