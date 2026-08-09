# ============================================================
# Indeed Collector
# ============================================================
# PURPOSE:
#   Searches Indeed.com and extracts structured job listings.
#   Uses the user's already-logged-in Chrome session.
# ============================================================

import asyncio
from typing import Optional
from collectors.base_collector import BaseCollector
from schemas.job_posting import JobPosting
from services.browser_service import BrowserService

# ============================================================
# CSS SELECTORS — Update these when Indeed changes its UI
# ============================================================

SELECTORS = {
    "job_cards": "div.job_seen_beacon",
    "card_title": "h2.jobTitle a, h2.jobTitle span[title]",
    "card_company": "span[data-testid='company-name']",
    "card_location": "div[data-testid='text-location']",
    "card_description": "div.job-snippet",
    "job_url": "h2.jobTitle a"
}


class IndeedCollector(BaseCollector):
    """
    Collects job listings from Indeed.com.
    """

    def __init__(self, browser: BrowserService):
        super().__init__(browser)
        self.platform_name = "indeed"

    # ================================================================
    # SEARCH — Navigate to Indeed and execute a job search
    # ================================================================

    async def search(self, page, query: str, location: str) -> None:
        """
        Search for jobs on Indeed.
        Uses URL parameters to bypass form interactions.
        """
        # Format for URL encoding
        import urllib.parse
        encoded_query = urllib.parse.quote_plus(query)
        encoded_location = urllib.parse.quote_plus(location)

        # Indeed search URL format (sorted by date)
        search_url = f"https://in.indeed.com/jobs?q={encoded_query}&l={encoded_location}&sort=date&fromage=2"  # Last 2 days

        # Navigate to search URL
        print(f"[{self.platform_name}] Navigating to: {search_url}")
        
        # Indeed can be slow/bot-protected
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"[{self.platform_name}] Note: page.goto threw an error (possibly a redirect or anti-bot): {e}")

        # Wait for either job cards to load OR a cloudflare challenge (which requires manual user click)
        try:
            await page.wait_for_selector(f"{SELECTORS['job_cards']}, iframe[src*='cloudflare']", timeout=15000)
            
            # Check if it's a Cloudflare challenge
            cf_iframe = await page.query_selector("iframe[src*='cloudflare']")
            if cf_iframe:
                print(f"\n[WARNING] INDEED ANTI-BOT DETECTED! 🚨")
                print("Indeed is asking for a Cloudflare check. Please open your Chrome window and click the checkbox manually!")
                print("Waiting 30 seconds for you to solve it...")
                await asyncio.sleep(30) # Give user time to click the box
                
        except Exception:
            print(f"[{self.platform_name}] Warning: Could not find job cards immediately. Page might be empty or loading slowly.")

    # ================================================================
    # EXTRACT — Parse job cards into JobPosting objects
    # ================================================================

    async def extract_listings(self, page) -> list[JobPosting]:
        """
        Extract all job listings from the current search results page.
        """
        jobs = []

        # Find all job cards on the page
        cards = await page.query_selector_all(SELECTORS["job_cards"])
        print(f"[{self.platform_name}] Found {len(cards)} job cards on page")

        for card in cards:
            try:
                # Scroll card into view to trigger lazy loading if needed
                await card.scroll_into_view_if_needed()

                # Extract basic info
                title_elem = await card.query_selector(SELECTORS["card_title"])
                company_elem = await card.query_selector(SELECTORS["card_company"])
                location_elem = await card.query_selector(SELECTORS["card_location"])
                desc_elem = await card.query_selector(SELECTORS["card_description"])

                title = await title_elem.inner_text() if title_elem else ""
                company = await company_elem.inner_text() if company_elem else ""
                location = await location_elem.inner_text() if location_elem else ""
                description = await desc_elem.inner_text() if desc_elem else ""

                # Extract Job URL (Very important for applying later)
                url_elem = await card.query_selector(SELECTORS["job_url"])
                url = ""
                if url_elem:
                    url = await url_elem.get_attribute("href")
                    if url and not url.startswith("http"):
                        url = f"https://in.indeed.com{url}"

                # Clean up extracted text
                title = title.strip()
                company = company.strip()
                location = location.strip()
                description = description.strip()

                # Skip empty or sponsored-only junk
                if not title or not company:
                    continue

                # Create JobPosting object
                job = JobPosting(
                    title=title,
                    company=company if company else None,
                    location=location if location else None,
                    description=description if description else None,
                    url=url,
                    platform=self.platform_name,
                )

                jobs.append(job)

            except Exception as e:
                print(f"[{self.platform_name}] Error extracting individual card: {e}")
                continue

        return jobs
