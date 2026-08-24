"""
Test: Open Google in your personal Edge browser via Playwright.
Uses YOUR logged-in profile (Default / Elbadaoui).
"""
import asyncio
from playwright.async_api import async_playwright
import base64

USER_DATA = "C:/Users/telba/AppData/Local/Microsoft/Edge/User Data"
PROFILE_DIR = "Default"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA,
            executable_path=EDGE_PATH,
            channel="msedge",
            headless=False,
            args=[f"--profile-directory={PROFILE_DIR}"],
        )
        print("✅ Edge launched with your Default profile (Elbadaoui)")

        page = await browser.new_page()
        await page.goto("https://www.google.com")
        title = await page.title()
        print(f"Title: {title}")

        cookies = await page.context.cookies()
        print(f"Cookies loaded from your profile: {len(cookies)}")

        # Screenshot
        await page.screenshot(path="edge_playwright_test.png")
        print("📸 Screenshot: edge_playwright_test.png")

        await browser.close()
        print()
        print("🎯 PLAYWRIGHT + YOUR PERSONAL BROWSER READY")
        print(f"   Edge: {EDGE_PATH}")
        print(f"   Profile: {PROFILE_DIR} (Elbadaoui)")


asyncio.run(main())
