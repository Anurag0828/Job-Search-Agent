# ============================================================
# LinkedIn Jobs Collector
# ============================================================
# PURPOSE:
#   Searches LinkedIn Jobs and extracts structured job listings.
#   Uses the user's already-logged-in Chrome session.
#
# HOW IT WORKS:
#   1. Opens a new tab in the user's Chrome
#   2. Goes to linkedin.com/jobs/search
#   3. Fills in the search query and location
#   4. Filters to "Past 24 hours" (only fresh jobs)
#   5. Scrolls through results, clicking each job to read details
#   6. Extracts: title, company, location, description, URL
#   7. Returns a list of JobPosting objects
#
# IMPORTANT:
#   - LinkedIn frequently changes its HTML structure
#   - If this collector breaks, update the CSS selectors below
#   - The selectors are gathered in one place (SELECTORS dict)
#     to make updates easy
# ============================================================

import asyncio
from typing import Optional
from collectors.base_collector import BaseCollector
from schemas.job_posting import JobPosting
from services.browser_service import BrowserService


# ============================================================
# CSS SELECTORS — All in one place for easy maintenance
# ============================================================
# When LinkedIn changes their website, update ONLY these selectors.
# The rest of the code stays the same.
# ============================================================

SELECTORS = {
    # Search form
    "search_keywords": 'input[id*="jobs-search-box-keyword"]',
    "search_location": 'input[id*="jobs-search-box-location"]',
    "search_button": 'button.jobs-search-box__submit-button',

    # Job listing cards (in the left sidebar)
    "job_cards": '.job-card-container',
    "job_card_link": 'a.job-card-container__link',
    "job_card_title": '.job-card-list__title--link span',
    "job_card_company": '.artdeco-entity-lockup__subtitle span',
    "job_card_location": '.artdeco-entity-lockup__caption span',
    "job_card_metadata": '.job-card-container__metadata-wrapper span',

    # Job detail panel (right side when you click a job)
    "detail_title": 'h1.t-24',
    "detail_company": '.job-details-jobs-unified-top-card__company-name a',
    "detail_location": '.job-details-jobs-unified-top-card__primary-description-container span',
    "detail_description": '.jobs-description__content',
    "detail_posted": '.job-details-jobs-unified-top-card__primary-description-container span',
    "detail_salary": '.job-details-jobs-unified-top-card__job-insight--highlight span',

    # Filters
    "date_filter_button": 'button[aria-label="Date posted filter."]',
    "past_24h_option": 'label[for*="past-24h"]',
    "apply_filter": 'button[data-control-name="filter_pill_apply"]',

    # Pagination
    "next_page": 'button[aria-label="View next page"], button.jobs-search-pagination__button--next',

    # Results count
    "results_count": '.jobs-search-results-list__subtitle',
}


class LinkedInJobsCollector(BaseCollector):
    """
    Collects job listings from LinkedIn Jobs.
    
    Inherits from BaseCollector, which means:
    - It MUST implement search() and extract_listings()
    - It gets collect() and collect_multiple_queries() for free
    
    Usage:
        async with BrowserService() as browser:
            collector = LinkedInJobsCollector(browser)
            jobs = await collector.collect("Python Developer", "Bangalore")
    """

    def __init__(self, browser: BrowserService):
        super().__init__(browser)
        self.platform_name = "linkedin_jobs"

    # ================================================================
    # SEARCH — Navigate to LinkedIn and execute a job search
    # ================================================================

    async def search(self, page, query: str, location: str) -> None:
        """
        Search for jobs on LinkedIn.
        
        Step-by-step:
            1. Navigate to LinkedIn Jobs search page
            2. Clear and fill the keyword field
            3. Clear and fill the location field
            4. Submit the search
            5. Wait for results to load
            6. Try to apply "Past 24 hours" filter
        """
        # Step 1: Navigate to LinkedIn Jobs (with 2-day recency filter)
        import urllib.parse
        encoded_q = urllib.parse.quote_plus(query)
        encoded_l = urllib.parse.quote_plus(location)
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={encoded_q}"
            f"&location={encoded_l}"
            f"&f_TPR=r172800"  # Past 2 days (172800 seconds)
            f"&f_E=2"          # Entry Level
        )
        print(f"[LinkedIn] Navigating to LinkedIn Jobs (last 2 days)...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"[LinkedIn] Note: page.goto threw an error (possibly a redirect): {e}")
        await self.browser.human_delay(2.0, 3.0)

        # Step 2: Fill in the search keyword
        print(f"[LinkedIn] Searching for: '{query}'...")
        try:
            # Try to find and fill the keyword input
            keyword_input = await page.query_selector(SELECTORS["search_keywords"])
            if keyword_input:
                await keyword_input.click()
                await keyword_input.fill("")  # Clear existing text
                await keyword_input.type(query, delay=50)  # Type like a human
                await self.browser.human_delay(0.5, 1.0)
        except Exception as e:
            print(f"[LinkedIn] Could not fill keyword field: {e}")
            # Fallback: Use URL-based search
            encoded_query = query.replace(" ", "%20")
            encoded_location = location.replace(" ", "%20")
            url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={encoded_query}"
                f"&location={encoded_location}"
                f"&f_TPR=r172800"  # Past 2 days
            )
            await page.goto(url, wait_until="domcontentloaded")
            await self.browser.human_delay(3.0, 5.0)
            return

        # Step 3: Fill in the location
        try:
            location_input = await page.query_selector(SELECTORS["search_location"])
            if location_input:
                await location_input.click()
                # Triple-click to select all existing text
                await location_input.click(click_count=3)
                await location_input.type(location, delay=50)
                await self.browser.human_delay(1.0, 2.0)
        except Exception as e:
            print(f"[LinkedIn] Could not fill location field: {e}")

        # Step 4: Submit search
        try:
            # Try clicking the search button
            await self.browser.wait_and_click(page, SELECTORS["search_button"], timeout=3000)
        except Exception:
            # Fallback: Press Enter
            await page.keyboard.press("Enter")

        # Step 5: Wait for results to load
        await self.browser.human_delay(3.0, 5.0)
        print(f"[LinkedIn] Search results loaded")

    # ================================================================
    # EXTRACT — Scrape job listings from the search results
    # ================================================================

    async def extract_listings(self, page) -> list[JobPosting]:
        """
        Extract job listings from LinkedIn search results page.
        
        LinkedIn shows jobs in two panels:
            LEFT:  A scrollable list of job cards (title, company, location)
            RIGHT: Detailed view when you click a card (full description)
        
        Our approach:
            1. Find all job cards on the left
            2. For each card, extract basic info (title, company, location)
            3. Click the card to load full details on the right
            4. Extract the full job description
            5. Build a JobPosting object
        """
        jobs: list[JobPosting] = []

        # Scroll the job list to load more results
        await self._scroll_job_list(page)

        # Find all job cards
        cards = await page.query_selector_all(SELECTORS["job_cards"])
        print(f"[LinkedIn] Found {len(cards)} job cards")

        for i, card in enumerate(cards):
            try:
                job = await self._extract_single_job(page, card, i)
                if job:
                    jobs.append(job)
            except Exception as e:
                print(f"[LinkedIn] Error extracting job {i + 1}: {e}")
                continue

        return jobs

    async def _extract_single_job(self, page, card, index: int) -> Optional[JobPosting]:
        """
        Extract data from a single job card.
        
        Args:
            page: The browser tab
            card: The job card element
            index: Card index (for logging)
        
        Returns:
            A JobPosting object, or None if extraction failed
        """
        # Extract basic info from the card
        title = ""
        company = ""
        location = ""
        job_url = ""

        # Get the job title
        title_el = await card.query_selector(SELECTORS["job_card_title"])
        if title_el:
            title = (await title_el.text_content()).strip()

        # Get the company name
        company_el = await card.query_selector(SELECTORS["job_card_company"])
        if company_el:
            company = (await company_el.text_content()).strip()

        # Get the location
        location_el = await card.query_selector(SELECTORS["job_card_location"])
        if location_el:
            location = (await location_el.text_content()).strip()

        # Get the job URL
        link_el = await card.query_selector(SELECTORS["job_card_link"])
        if link_el:
            href = await link_el.get_attribute("href")
            if href:
                # LinkedIn URLs may be relative — make them absolute
                if href.startswith("/"):
                    job_url = f"https://www.linkedin.com{href}"
                else:
                    job_url = href
                # Clean the URL (remove tracking parameters)
                job_url = job_url.split("?")[0] if "?" in job_url else job_url

        # Skip if we couldn't get the basics
        if not title or not job_url:
            return None

        # Click the card to load the full job description
        description = ""
        posted_date = ""
        salary = ""

        try:
            await card.click()
            await self.browser.human_delay(1.0, 2.0)

            # Extract full description from the detail panel
            desc_el = await page.query_selector(SELECTORS["detail_description"])
            if desc_el:
                description = (await desc_el.text_content()).strip()

            # Try to get salary info
            salary_el = await page.query_selector(SELECTORS["detail_salary"])
            if salary_el:
                salary = (await salary_el.text_content()).strip()

        except Exception as e:
            # If clicking fails, we still have the basic info
            print(f"[LinkedIn] Could not load details for job {index + 1}: {e}")

        # Extract platform-specific job ID from URL
        platform_job_id = ""
        if "/view/" in job_url:
            platform_job_id = job_url.split("/view/")[-1].split("/")[0]

        # Build the JobPosting object
        job = JobPosting(
            title=title,
            company=company if company else None,
            location=location if location else None,
            description=description if description else None,
            url=job_url,
            posted_date=posted_date if posted_date else None,
            salary=salary if salary else None,
            platform="linkedin_jobs",
            platform_job_id=platform_job_id if platform_job_id else None,
        )

        print(f"  [{index + 1}] {title} @ {company}")
        return job

    async def _scroll_job_list(self, page) -> None:
        """
        Scroll the LinkedIn job list sidebar to load more results.
        
        LinkedIn lazy-loads jobs — only ~7 are visible initially.
        Scrolling the sidebar loads more (up to 25 per page).
        """
        try:
            # Scroll down in the job list 3 times by scrolling the last card into view
            for _ in range(3):
                cards = await page.query_selector_all(SELECTORS["job_cards"])
                if cards:
                    last_card = cards[-1]
                    await last_card.scroll_into_view_if_needed()
                    await self.browser.human_delay(1.5, 2.5)
        except Exception as e:
            print(f"[LinkedIn] Scroll warning: {e}")
            # If scrolling fails, just proceed with whatever jobs are visible
            pass

    async def go_to_next_page(self, page) -> bool:
        """
        Navigate to the next page of LinkedIn search results.
        
        LinkedIn uses numbered pagination buttons at the bottom.
        """
        try:
            clicked = await self.browser.wait_and_click(
                page, SELECTORS["next_page"], timeout=3000
            )
            if clicked:
                await self.browser.human_delay(3.0, 5.0)
                return True
        except Exception:
            pass
        return False
