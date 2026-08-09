# ============================================================
# Base Collector — Interface All Platform Collectors Follow
# ============================================================
# PURPOSE:
#   Defines the CONTRACT that every collector must implement.
#   LinkedIn, Naukri, Indeed collectors all follow this same pattern.
#
# WHY AN INTERFACE?
#   Without it, each collector could have different method names:
#     linkedin.search_jobs()
#     naukri.find_positions()
#     indeed.get_listings()
#   
#   The Supervisor would need special code for each one!
#
#   With a base class, they all have the same methods:
#     linkedin.collect() → list[JobPosting]
#     naukri.collect()   → list[JobPosting]
#     indeed.collect()   → list[JobPosting]
#   
#   The Supervisor just loops: for collector in collectors: collector.collect()
#
# HOW TO ADD A NEW PLATFORM:
#   1. Create collectors/glassdoor.py
#   2. Make it inherit from BaseCollector
#   3. Implement search() and extract_listings()
#   4. That's it — no changes to Supervisor or Matching Agent
# ============================================================

from abc import ABC, abstractmethod
from typing import Optional
from schemas.job_posting import JobPosting
from services.browser_service import BrowserService
from datetime import datetime


class BaseCollector(ABC):
    """
    Abstract base class for all platform collectors.
    
    Every collector (LinkedIn, Naukri, Indeed) inherits from this
    and must implement the abstract methods marked with @abstractmethod.
    
    Think of this as a TEMPLATE:
        "Every collector must be able to search and extract listings.
         HOW they do it is up to them (each platform is different),
         but WHAT they produce is the same: list[JobPosting]."
    """

    def __init__(self, browser: BrowserService):
        """
        Initialize the collector with a browser service.
        
        Args:
            browser: The shared BrowserService that manages Chrome connection.
                    All collectors use the same browser, but each gets its own tab.
        """
        self.browser = browser
        self.platform_name: str = "unknown"  # Override in subclass

    # ================================================================
    # ABSTRACT METHODS — Subclasses MUST implement these
    # ================================================================

    @abstractmethod
    async def search(self, page, query: str, location: str) -> None:
        """
        Navigate to the platform and execute a job search.
        
        This is different for each platform:
            LinkedIn: Go to linkedin.com/jobs, fill search box, click search
            Naukri:   Go to naukri.com, fill search box, click search
            Indeed:   Go to indeed.com, fill search box, click search
        
        Args:
            page: Playwright page (browser tab) to use
            query: Job title to search for (e.g., "Python Developer")
            location: Location to search in (e.g., "Bangalore")
        """
        pass

    @abstractmethod
    async def extract_listings(self, page) -> list[JobPosting]:
        """
        Extract job listings from the current search results page.
        
        This is different for each platform because each has different
        HTML structure. But the OUTPUT is always the same: list[JobPosting].
        
        Args:
            page: Playwright page showing search results
        
        Returns:
            List of JobPosting objects in the common schema
        """
        pass

    # ================================================================
    # SHARED METHODS — Common logic used by all collectors
    # ================================================================

    async def collect(
        self,
        query: str,
        location: str,
        max_pages: int = 3,
    ) -> list[JobPosting]:
        """
        Full collection pipeline: open tab → search → extract → close tab.
        
        This is what the Supervisor calls. It orchestrates the entire
        collection process for this platform.
        
        Args:
            query: Job title to search (e.g., "Backend Engineer")
            location: Location to search (e.g., "Bangalore")
            max_pages: How many pages of results to scrape (default: 3)
        
        Returns:
            List of JobPosting objects found on this platform
        
        Flow:
            1. Open new browser tab
            2. Navigate to platform and search
            3. Extract job listings from results
            4. Close the tab
            5. Return the collected jobs
        """
        all_jobs: list[JobPosting] = []
        page = None

        try:
            print(f"\n[{self.platform_name}] Starting collection...")
            print(f"[{self.platform_name}] Query: '{query}' | Location: '{location}'")

            # Step 1: Open a new tab
            page = await self.browser.new_page()

            # Step 2: Execute the search
            await self.search(page, query, location)
            print(f"[{self.platform_name}] Search executed successfully")

            # Step 3: Add a human-like delay after search
            await self.browser.human_delay(2.0, 4.0)

            # Step 4: Extract listings from results (potentially multiple pages)
            for page_num in range(1, max_pages + 1):
                print(f"[{self.platform_name}] Extracting page {page_num}...")

                # Extract jobs from current page
                jobs = await self.extract_listings(page)
                all_jobs.extend(jobs)
                print(f"[{self.platform_name}] Found {len(jobs)} jobs on page {page_num}")

                # Try to go to next page (if available)
                if page_num < max_pages:
                    has_next = await self.go_to_next_page(page)
                    if not has_next:
                        print(f"[{self.platform_name}] No more pages")
                        break
                    await self.browser.human_delay(2.0, 4.0)

            # Stamp each job with collection metadata
            for job in all_jobs:
                job.platform = self.platform_name
                job.collected_at = datetime.now()

            print(f"[{self.platform_name}] Collection complete: {len(all_jobs)} total jobs")

        except Exception as e:
            print(f"[{self.platform_name}] ERROR during collection: {str(e)}")
            # Don't crash — return whatever we managed to collect
            # The Supervisor will note this as a partial failure

        finally:
            # Step 5: Always close the tab when done
            if page:
                await page.close()
                print(f"[{self.platform_name}] Tab closed")

        return all_jobs

    async def go_to_next_page(self, page) -> bool:
        """
        Try to navigate to the next page of results.
        
        Override this in subclasses if the platform has a specific
        pagination mechanism. Default implementation looks for common
        "Next" button patterns.
        
        Returns:
            True if successfully navigated to next page, False if no next page
        """
        # Try common "Next" button selectors
        next_selectors = [
            'button[aria-label="Next"]',
            'a[aria-label="Next"]',
            'button.next',
            'a.next',
            'li.next a',
            '[data-testid="pagination-next"]',
        ]

        for selector in next_selectors:
            clicked = await self.browser.wait_and_click(page, selector, timeout=3000)
            if clicked:
                # Wait for the new page to load
                await self.browser.human_delay(2.0, 4.0)
                return True

        return False

    async def collect_multiple_queries(
        self,
        queries: list[str],
        locations: list[str],
        max_pages: int = 2,
    ) -> list[JobPosting]:
        """
        Run collection for MULTIPLE search queries and locations.
        
        If you're searching for both "Python Developer" and "Backend Engineer"
        in both "Bangalore" and "Remote", this runs all 4 combinations:
            1. "Python Developer" in "Bangalore"
            2. "Python Developer" in "Remote"
            3. "Backend Engineer" in "Bangalore"
            4. "Backend Engineer" in "Remote"
        
        Args:
            queries: List of job titles to search
            locations: List of locations to search
            max_pages: Pages per search
        
        Returns:
            Combined list of all jobs found across all searches
        """
        all_jobs: list[JobPosting] = []

        for query in queries:
            for location in locations:
                jobs = await self.collect(query, location, max_pages)
                all_jobs.extend(jobs)

        # Remove exact URL duplicates (same job found in multiple searches)
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)

        print(f"[{self.platform_name}] Total unique jobs: {len(unique_jobs)} "
              f"(removed {len(all_jobs) - len(unique_jobs)} duplicates)")
        return unique_jobs
