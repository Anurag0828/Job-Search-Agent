# ============================================================
# Browser Service — Playwright-Native Browser Manager
# ============================================================
# PURPOSE:
#   Launches Playwright's own Chromium browser with saved login
#   sessions (auth.json). No external Chrome needed.
#
# HOW IT WORKS:
#   1. You run "python cli.py login" ONCE to log into LinkedIn,
#      Naukri, Indeed in a visible browser window.
#   2. Playwright saves your cookies/sessions to auth.json.
#   3. From then on, the agent launches its own headless browser
#      using auth.json — no Chrome needed, works on cloud too.
#
# SECURITY:
#   - auth.json is in .gitignore (never uploaded to GitHub)
#   - Cookies expire naturally; re-run "cli.py login" to refresh
#   - Works identically on laptop and cloud VPS
#
# USAGE:
#   from services.browser_service import BrowserService
#
#   async with BrowserService() as browser:
#       page = await browser.new_page()
#       await page.goto("https://linkedin.com/jobs")
#       # ... scrape data ...
#       await page.close()
# ============================================================

import os
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from config.settings import settings

# Path to the saved session file
AUTH_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "auth.json")


class BrowserService:
    """
    Manages Playwright's built-in Chromium browser.

    Uses saved session state (auth.json) to browse job platforms
    as the logged-in user, without needing Chrome to be open.
    """

    def __init__(self):
        """Initialize the browser service (does NOT launch yet)."""
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._connected = False

    # ================================================================
    # CONNECTION MANAGEMENT
    # ================================================================

    async def connect(self) -> None:
        """
        Launch Playwright's Chromium browser with saved login sessions.

        HOW IT WORKS:
            1. Starts Playwright engine
            2. Launches a Chromium browser (headless by default)
            3. Loads auth.json (your saved LinkedIn/Naukri/Indeed logins)
            4. Collectors can now browse as if they were you

        If auth.json doesn't exist, it raises a clear error telling
        the user to run "python cli.py login" first.
        """
        print("[Browser] Launching Playwright Chromium...")

        try:
            # Start Playwright
            self._playwright = await async_playwright().start()

            # Launch Playwright's own Chromium (NOT your Chrome) - HEADFUL to avoid bot detection
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )

            # Common realistic user agent
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"

            # Load saved session if auth.json exists
            if os.path.exists(AUTH_FILE):
                print(f"[Browser] Loading saved login session from auth.json...")
                self._context = await self._browser.new_context(storage_state=AUTH_FILE, user_agent=ua)
                print("[Browser] Session loaded! Browsing as logged-in user.")
            else:
                print("[Browser] No auth.json found. Browsing without login.")
                print("[Browser] TIP: Run 'python cli.py login' to save your logins!")
                self._context = await self._browser.new_context(user_agent=ua)

            self._connected = True
            print("[Browser] Browser ready!")

        except Exception as e:
            if self._playwright:
                await self._playwright.stop()
            raise ConnectionError(
                f"\n"
                f"[Browser] Failed to launch Playwright Chromium.\n"
                f"Error: {str(e)}\n"
                f"\n"
                f"Make sure Playwright browsers are installed:\n"
                f"  python -m playwright install chromium\n"
            )

    # ================================================================
    # LOGIN SESSION MANAGEMENT
    # ================================================================

    @staticmethod
    async def interactive_login():
        """
        Open a VISIBLE browser window for the user to manually log
        into LinkedIn, Naukri, and Indeed. Once done, saves the
        session cookies to auth.json.

        This is a one-time setup step. After this, the agent can
        browse headlessly using the saved session.
        """
        print("\n" + "=" * 60)
        print("  INTERACTIVE LOGIN SESSION")
        print("=" * 60)
        print()
        print("A Chromium browser window will open.")
        print("Please log into these sites:")
        print("  1. LinkedIn  (linkedin.com)")
        print("  2. Naukri    (naukri.com)")
        print("  3. Indeed    (indeed.com)")
        print()
        print("Once you are logged into ALL three, come back here")
        print("and press ENTER to save your session.")
        print("=" * 60)

        pw = await async_playwright().start()

        # Launch a VISIBLE browser (headless=False) so user can interact
        # Use a real user-agent so sites don't block us with "not secure" warnings
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        )

        # Open tabs for each platform — handle timeouts gracefully
        sites = [
            ("LinkedIn", "https://www.linkedin.com/login"),
            ("Naukri", "https://www.naukri.com/mnjuser/login"),
            ("Indeed", "https://in.indeed.com/"),
        ]

        for name, url in sites:
            try:
                page = await context.new_page()
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                print(f"  [OK] {name} tab opened successfully")
            except Exception as e:
                print(f"  [WARN] {name} was slow to load — that's OK, you can navigate manually in the browser")

        # Wait for user to finish logging in
        print("\n[WAITING] Log into all sites in the browser window...")
        print("[WAITING] Take your time. When done, press ENTER here...")

        # Use asyncio-compatible input waiting
        await asyncio.get_event_loop().run_in_executor(None, input)

        # Save the session state (cookies, localStorage, etc.)
        await context.storage_state(path=AUTH_FILE)

        print(f"\n[SUCCESS] Login session saved to auth.json!")
        print("[SUCCESS] Your agent can now browse as you without Chrome!")
        print("[SUCCESS] This works on your laptop AND on a cloud server!")

        await browser.close()
        await pw.stop()

    async def disconnect(self) -> None:
        """
        Disconnect from Chrome (does NOT close your Chrome browser).
        
        Your Chrome keeps running normally after we disconnect.
        """
        if self._browser:
            # We only disconnect — we do NOT close the browser
            # because it's the user's Chrome with their tabs
            await self._browser.close()
            self._browser = None
            self._context = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        self._connected = False
        print("[Browser] Disconnected from Chrome")

    # ================================================================
    # PAGE (TAB) MANAGEMENT
    # ================================================================

    async def new_page(self) -> Page:
        """
        Open a new tab in the user's Chrome browser.
        
        Each collector gets its own tab so they don't interfere
        with each other or with the user's browsing.
        
        Returns:
            A Playwright Page object (represents one browser tab)
        
        Usage:
            page = await browser.new_page()
            await page.goto("https://linkedin.com/jobs")
            content = await page.content()
            await page.close()  # Clean up when done
        """
        if not self._connected:
            await self.connect()

        page = await self._context.new_page()
        print("[Browser] Opened new tab")
        return page

    # ================================================================
    # HELPER METHODS — Used by collectors for common browser tasks
    # ================================================================

    async def wait_and_click(self, page: Page, selector: str, timeout: int = 10000) -> bool:
        """
        Wait for an element to appear, then click it.
        
        Args:
            page: The browser tab
            selector: CSS selector for the element (e.g., "button.apply-btn")
            timeout: Max milliseconds to wait (default 10 seconds)
        
        Returns:
            True if clicked successfully, False if element not found
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            await page.click(selector)
            return True
        except Exception:
            print(f"[Browser] Element not found: {selector}")
            return False

    async def safe_get_text(self, page: Page, selector: str, default: str = "") -> str:
        """
        Safely extract text from an element. Returns default if not found.
        
        This is used heavily by collectors to extract job details.
        Instead of crashing when an element is missing, it returns
        a default value (empty string).
        
        Args:
            page: The browser tab
            selector: CSS selector for the element
            default: What to return if the element doesn't exist
        
        Returns:
            The text content of the element, or the default value
        """
        try:
            element = await page.query_selector(selector)
            if element:
                return (await element.text_content()).strip()
            return default
        except Exception:
            return default

    async def safe_get_attribute(self, page: Page, selector: str, attribute: str, default: str = "") -> str:
        """
        Safely extract an attribute from an element. Returns default if not found.
        
        Useful for extracting URLs from href attributes:
            url = await browser.safe_get_attribute(page, "a.job-link", "href")
        """
        try:
            element = await page.query_selector(selector)
            if element:
                value = await element.get_attribute(attribute)
                return value.strip() if value else default
            return default
        except Exception:
            return default

    async def scroll_to_bottom(self, page: Page, pause_seconds: float = 1.5) -> None:
        """
        Scroll to the bottom of the page to load lazy-loaded content.
        
        Many job platforms use "infinite scroll" — more jobs load as
        you scroll down. This simulates that scrolling.
        """
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(pause_seconds)

    async def human_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """
        Wait a random amount of time (to appear human, not bot-like).
        
        Platforms detect bots by looking for inhuman speed.
        A real person doesn't click exactly every 1.000 seconds.
        This adds randomness: sometimes 1.2s, sometimes 2.8s.
        """
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    # ================================================================
    # CONTEXT MANAGER — Allows "async with BrowserService() as browser:"
    # ================================================================

    async def __aenter__(self):
        """Called when entering 'async with BrowserService() as browser:'"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Called when exiting the 'async with' block — auto-disconnects."""
        await self.disconnect()
