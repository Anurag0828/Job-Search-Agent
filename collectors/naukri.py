# ============================================================
# Naukri Collector
# ============================================================
# PURPOSE:
#   Searches Naukri.com and extracts structured job listings.
#   Uses the user's already-logged-in Chrome session.
#
# HOW IT WORKS:
#   1. Opens a new tab in the user's Chrome
#   2. Goes to naukri.com search URL with query parameters
#   3. Extracts job cards from the results page
#   4. For each job, extracts: title, company, location, description, URL
#   5. Returns a list of JobPosting objects
#
# NAUKRI-SPECIFIC NOTES:
#   - Naukri uses URL-based search (easier than form-filling)
#   - Job cards contain most info directly (no need to click each one)
#   - Naukri's HTML structure uses class names with "tuple" prefix
# ============================================================

import asyncio
from typing import Optional
from collectors.base_collector import BaseCollector
from schemas.job_posting import JobPosting
from services.browser_service import BrowserService


# ============================================================
# CSS SELECTORS — Update these when Naukri changes its UI
# ============================================================

SELECTORS = {
    # Job listing cards — multiple strategies (Naukri changes these frequently)
    "job_cards": 'article.jobTuple',
    "job_cards_alt": 'div[class*="jobTuple"], div[class*="srp-jobtuple"]',
    "job_cards_modern": 'div[data-job-id], div[class*="cust-job-tuple"]',
    "job_cards_generic": 'div.list > div[class*="tuple"], div.srp-jobtuple-wrapper article',

    # Within each card — title
    "card_title": 'a.title, a[class*="title"], h2 a',
    "card_title_alt": 'a[class*="jobTitle"], a[class*="job-title"], div[class*="title"] a',

    # Within each card — company
    "card_company": 'a.comp-name, a[class*="companyName"], span.comp-name, a[class*="comp-name"], span[class*="company"]',

    # Within each card — location
    "card_location": 'span.loc, span.locWdth, span[class*="location"], span[class*="loc-"]',

    # Within each card — salary
    "card_salary": 'span.sal, span[class*="salary"], span[class*="sal-"]',

    # Within each card — experience
    "card_experience": 'span.exp, span[class*="experience"], span[class*="exp-"]',

    # Within each card — description
    "card_description": 'div.job-description, div[class*="jobDescription"], div[class*="job-desc"]',

    # Within each card — posted date
    "card_posted": 'span.date, span[class*="posted"], span[class*="date"], span[class*="freshness"]',

    # Within each card — tags
    "card_tags": 'ul.tags li, span[class*="tag"]',

    # Pagination
    "next_page": 'a.fright.fs14.btn-secondary, a[class*="next"], a[class*="nxtBtn"]',
}


class NaukriCollector(BaseCollector):
    """
    Collects job listings from Naukri.com.
    
    Naukri is one of India's largest job platforms.
    This collector uses URL-based search (simpler and more reliable
    than form-filling) because Naukri's search URLs are predictable.
    
    Usage:
        async with BrowserService() as browser:
            collector = NaukriCollector(browser)
            jobs = await collector.collect("Python Developer", "Bangalore")
    """

    def __init__(self, browser: BrowserService):
        super().__init__(browser)
        self.platform_name = "naukri"

    # ================================================================
    # SEARCH — Navigate to Naukri and execute a job search
    # ================================================================

    async def search(self, page, query: str, location: str) -> None:
        """
        Search for jobs on Naukri.
        
        Instead of filling forms, we construct the search URL directly.
        This is more reliable because Naukri's forms can be tricky with
        auto-complete dropdowns.
        
        Naukri URL pattern:
            https://www.naukri.com/{query}-jobs-in-{location}
        
        Example:
            https://www.naukri.com/python-developer-jobs-in-bangalore
        """
        # Build the search URL
        # Naukri uses hyphens in URLs: "Python Developer" → "python-developer"
        formatted_query = query.lower().replace(" ", "-")
        formatted_location = location.lower().replace(" ", "-")

        # Naukri search URL format with Entry Level experience filter
        search_url = (
            f"https://www.naukri.com/{formatted_query}-jobs-in-{formatted_location}-0-to-2-years"
            f"?jobAge=2"  # Filter: Posted in last 2 days
        )

        print(f"[Naukri] Navigating to: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded")
        await self.browser.human_delay(3.0, 5.0)

        # Close any popups that Naukri shows (login prompts, notifications)
        await self._dismiss_popups(page)

        print(f"[Naukri] Search results loaded")

    # ================================================================
    # EXTRACT — Scrape job listings from search results
    # ================================================================

    async def extract_listings(self, page) -> list[JobPosting]:
        """
        Extract job listings from Naukri search results.
        
        Naukri shows all job info directly on the search page
        (unlike LinkedIn where you need to click each card).
        This makes extraction simpler and faster.
        """
        jobs: list[JobPosting] = []

        # Scroll to load all results on the page
        await self.browser.scroll_to_bottom(page)
        await self.browser.human_delay(1.0, 2.0)

        # Try multiple selector strategies (Naukri changes its HTML frequently)
        cards = await page.query_selector_all(SELECTORS["job_cards"])
        if not cards:
            cards = await page.query_selector_all(SELECTORS["job_cards_alt"])
        if not cards:
            cards = await page.query_selector_all(SELECTORS["job_cards_modern"])
        if not cards:
            cards = await page.query_selector_all(SELECTORS["job_cards_generic"])

        print(f"[Naukri] Found {len(cards)} job cards")

        for i, card in enumerate(cards):
            try:
                job = await self._extract_single_job(card, i)
                if job:
                    jobs.append(job)
            except Exception as e:
                print(f"[Naukri] Error extracting job {i + 1}: {e}")
                continue

        return jobs

    async def _extract_single_job(self, card, index: int) -> Optional[JobPosting]:
        """
        Extract data from a single Naukri job card.
        
        Naukri cards contain:
            - Title (as a link)
            - Company name
            - Location
            - Experience required
            - Salary (sometimes)
            - Brief description
            - Posted date
        """
        # Extract title and URL
        title = ""
        job_url = ""

        # Try multiple title selectors
        for selector in [SELECTORS["card_title"], SELECTORS["card_title_alt"]]:
            # Each selector string may contain commas (CSS selector list),
            # so we try them as-is
            title_el = await card.query_selector(selector)
            if title_el:
                title = (await title_el.text_content()).strip()
                href = await title_el.get_attribute("href")
                if href:
                    job_url = href if href.startswith("http") else f"https://www.naukri.com{href}"
                break

        # If still no URL, try finding any link in the card
        if not job_url:
            any_link = await card.query_selector('a[href*="naukri.com"]')
            if any_link:
                href = await any_link.get_attribute("href")
                if href:
                    job_url = href if href.startswith("http") else f"https://www.naukri.com{href}"
                if not title:
                    title = (await any_link.text_content()).strip()

        # Skip if no title or URL found
        if not title or not job_url:
            return None

        # Extract company name
        company = ""
        company_el = await card.query_selector(SELECTORS["card_company"])
        if company_el:
            company = (await company_el.text_content()).strip()

        # Extract location
        location = ""
        location_el = await card.query_selector(SELECTORS["card_location"])
        if location_el:
            location = (await location_el.text_content()).strip()

        # Extract salary
        salary = ""
        salary_el = await card.query_selector(SELECTORS["card_salary"])
        if salary_el:
            salary = (await salary_el.text_content()).strip()

        # Extract experience
        experience = ""
        exp_el = await card.query_selector(SELECTORS["card_experience"])
        if exp_el:
            experience = (await exp_el.text_content()).strip()

        # Extract description snippet
        description = ""
        desc_el = await card.query_selector(SELECTORS["card_description"])
        if desc_el:
            description = (await desc_el.text_content()).strip()

        # Extract posted date
        posted_date = ""
        posted_el = await card.query_selector(SELECTORS["card_posted"])
        if posted_el:
            posted_date = (await posted_el.text_content()).strip()

        # Extract platform-specific job ID from URL
        platform_job_id = ""
        if "jd/" in job_url:
            # Naukri URLs look like: naukri.com/job-listings-...-jd-12345
            parts = job_url.split("-jd-")
            if len(parts) > 1:
                platform_job_id = parts[-1].split("?")[0]

        # Add experience info to description if available
        if experience and description:
            description = f"Experience: {experience}\n\n{description}"
        elif experience:
            description = f"Experience: {experience}"

        # Build the JobPosting
        job = JobPosting(
            title=title,
            company=company if company else None,
            location=location if location else None,
            description=description if description else None,
            url=job_url,
            posted_date=posted_date if posted_date else None,
            salary=salary if salary else None,
            platform="naukri",
            platform_job_id=platform_job_id if platform_job_id else None,
        )

        print(f"  [{index + 1}] {title} @ {company}")
        return job

    async def _dismiss_popups(self, page) -> None:
        """
        Close common Naukri popups that appear on page load.
        
        Naukri often shows:
        - Login/signup prompts
        - Notification permission requests
        - App download banners
        """
        popup_close_selectors = [
            'button[class*="close"]',
            'span[class*="close"]',
            'div[class*="crossIcon"]',
            'button[title="Close"]',
            '.chatbot_closeButton',
        ]

        for selector in popup_close_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    if await el.is_visible():
                        await el.click()
                        await asyncio.sleep(0.5)
            except Exception:
                pass  # Ignore if popup close fails

    async def go_to_next_page(self, page) -> bool:
        """Navigate to the next page of Naukri search results."""
        try:
            clicked = await self.browser.wait_and_click(
                page, SELECTORS["next_page"], timeout=3000
            )
            if clicked:
                await self.browser.human_delay(3.0, 5.0)
                await self._dismiss_popups(page)
                return True
        except Exception:
            pass
        return False
