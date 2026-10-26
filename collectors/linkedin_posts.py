# ============================================================
# LinkedIn Posts Collector — Scrapes HR Hiring Posts from Feed
# ============================================================
# PURPOSE:
#   Many recruiters post job openings as LinkedIn feed posts
#   instead of formal job listings. This collector finds those posts.
#
# WHAT IT LOOKS FOR:
#   Posts containing hiring signals like:
#     - "We're hiring", "looking for", "open position"
#     - "DM me", "send your resume", "apply now"
#     - "#hiring", "#opentowork", "#jobs"
#
# HOW IT WORKS:
#   1. Opens LinkedIn feed in the user's authenticated browser
#   2. Searches for posts with hiring-related keywords
#   3. Scrolls through results, extracting post content
#   4. Uses LLM to extract structured job info from unstructured posts
#   5. Returns JobPosting objects with platform="linkedin_posts"
#
# DATA FLOW:
#   LinkedIn Feed → scroll & extract posts → LLM structures them
#       → JobPosting objects → saved to database
# ============================================================

import asyncio
import re
from typing import Optional
from collectors.base_collector import BaseCollector
from schemas.job_posting import JobPosting
from services.browser_service import BrowserService


# Hiring signal keywords to search for in LinkedIn
HIRING_SEARCH_QUERIES = [
    "hiring AI engineer India",
    "hiring GenAI engineer",
    "looking for ML engineer",
    "hiring python developer AI",
    "open position AI engineer remote",
]

# Regex patterns to detect hiring intent in post text
HIRING_SIGNALS = re.compile(
    r"(we.re hiring|we are hiring|looking for|open position|"
    r"open role|join our team|join us|come work with|"
    r"hiring alert|job opening|dm me|send your resume|"
    r"apply now|reach out|interested candidates|"
    r"#hiring|#opentowork|#jobs|#careers)",
    re.IGNORECASE
)

# Patterns to extract HR contact info from posts
EMAIL_PATTERN = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
LINKEDIN_DM_SIGNAL = re.compile(
    r"(dm me|message me|reach out|send me a message|drop me a message|inbox me)",
    re.IGNORECASE
)


class LinkedInPostsCollector(BaseCollector):
    """
    Scrapes LinkedIn feed posts where HRs announce job openings.
    
    Unlike LinkedInJobsCollector which scrapes formal job listings,
    this collector targets the LinkedIn feed/search where recruiters
    post informal hiring announcements.
    """
    
    platform_name = "linkedin_posts"
    
    async def collect(self, browser_service: BrowserService, search_queries: list[str] = None, locations: list[str] = None) -> list[JobPosting]:
        """
        Main collection method. Searches LinkedIn for hiring posts.
        
        Args:
            browser_service: The authenticated browser service
            search_queries: Job titles to search for (from .env)
            locations: Locations to filter by (from .env)
            
        Returns:
            List of JobPosting objects extracted from hiring posts
        """
        all_jobs = []
        page = None
        
        try:
            context = browser_service.context
            if not context:
                print("[LinkedIn Posts] No browser context available")
                return []
            
            page = await context.new_page()
            
            # Use hiring-specific search queries
            queries_to_search = HIRING_SEARCH_QUERIES[:3]  # Limit to avoid detection
            
            for query in queries_to_search:
                try:
                    posts = await self._search_and_extract(page, query)
                    all_jobs.extend(posts)
                    print(f"[LinkedIn Posts] Found {len(posts)} posts for: '{query}'")
                    
                    # Human-like delay between searches
                    await asyncio.sleep(3.0)
                except Exception as e:
                    print(f"[LinkedIn Posts] Error searching '{query}': {e}")
                    continue
            
            print(f"[LinkedIn Posts] Total posts collected: {len(all_jobs)}")
            
        except Exception as e:
            print(f"[LinkedIn Posts] Collection failed: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except:
                    pass
        
        return all_jobs
    
    async def _search_and_extract(self, page, query: str) -> list[JobPosting]:
        """
        Search LinkedIn for a query and extract hiring posts from results.
        """
        jobs = []
        
        # Navigate to LinkedIn search with content filter
        search_url = f"https://www.linkedin.com/search/results/content/?keywords={query.replace(' ', '%20')}&origin=GLOBAL_SEARCH_HEADER&sortBy=date_posted"
        
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3.0)
        
        # Scroll to load more posts (3 scrolls)
        for scroll in range(3):
            await page.evaluate("window.scrollBy(0, 1500)")
            await asyncio.sleep(2.0)
        
        # Extract post containers
        post_elements = await page.query_selector_all('.feed-shared-update-v2, .update-components-actor, div[data-urn]')
        
        if not post_elements:
            # Fallback: try broader selectors
            post_elements = await page.query_selector_all('.search-results__cluster-content div.mb1')
        
        print(f"[LinkedIn Posts] Found {len(post_elements)} post elements for '{query}'")
        
        # Extract text from each post
        for i, element in enumerate(post_elements[:15]):  # Limit to 15 per search
            try:
                post_data = await self._extract_post_data(page, element, i)
                if post_data:
                    jobs.append(post_data)
            except Exception as e:
                continue
        
        return jobs
    
    async def _extract_post_data(self, page, element, index: int) -> Optional[JobPosting]:
        """
        Extract structured data from a single LinkedIn post element.
        """
        try:
            # Get the full text content of the post
            post_text = await element.inner_text()
            
            if not post_text or len(post_text) < 50:
                return None
            
            # Check if this post has hiring signals
            if not HIRING_SIGNALS.search(post_text):
                return None
            
            # Extract poster info
            poster_name = "Unknown Recruiter"
            poster_elements = await element.query_selector_all('.update-components-actor__name span, .feed-shared-actor__name span')
            if poster_elements:
                poster_name = await poster_elements[0].inner_text()
                poster_name = poster_name.strip()
            
            # Extract any email addresses from the post
            emails_found = EMAIL_PATTERN.findall(post_text)
            hr_email = emails_found[0] if emails_found else None
            
            # Check for DM signals
            dm_signal = bool(LINKEDIN_DM_SIGNAL.search(post_text))
            
            # Build application method
            if hr_email:
                application_method = f"Email resume to {hr_email}"
            elif dm_signal:
                application_method = f"DM {poster_name} on LinkedIn"
            else:
                application_method = "Apply via LinkedIn"
            
            # Try to get the post URL
            post_url = ""
            link_elements = await element.query_selector_all('a[href*="/feed/update/"]')
            if link_elements:
                post_url = await link_elements[0].get_attribute("href")
                if post_url and not post_url.startswith("http"):
                    post_url = f"https://www.linkedin.com{post_url}"
            
            if not post_url:
                post_url = f"https://www.linkedin.com/feed/update/post-{index}"
            
            # Extract job title from post text using simple heuristics
            title = self._extract_title_from_post(post_text)
            company = self._extract_company_from_post(post_text, poster_name)
            
            # Truncate description to reasonable length
            description = post_text[:3000].strip()
            
            # Add HR contact info to description for downstream processing
            if hr_email or dm_signal:
                description += f"\n\n--- CONTACT INFO ---\n"
                description += f"Application Method: {application_method}\n"
                if hr_email:
                    description += f"HR Email: {hr_email}\n"
                description += f"Posted by: {poster_name}\n"
            
            return JobPosting(
                title=title,
                company=company,
                location="India",  # Default, will be refined by LLM
                description=description,
                url=post_url,
                platform="linkedin_posts",
                posted_date="Recent",
            )
            
        except Exception as e:
            return None
    
    def _extract_title_from_post(self, text: str) -> str:
        """
        Extract a job title from unstructured post text using regex patterns.
        """
        # Common patterns: "Hiring for Senior AI Engineer", "Looking for a ML Engineer"
        patterns = [
            r"(?:hiring|looking for|need|seeking|want)\s+(?:a\s+|an\s+)?(.{10,60}?)(?:\.|,|\n|!|at\s|in\s|with\s)",
            r"(?:position|role|opening)\s*(?:of|for|:)\s*(.{10,60}?)(?:\.|,|\n|!)",
            r"(?:join us as|join our team as)\s+(?:a\s+|an\s+)?(.{10,60}?)(?:\.|,|\n|!)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Clean up common artifacts
                title = re.sub(r'\s+', ' ', title)
                if len(title) > 10:
                    return title[:80]
        
        # Fallback: use first meaningful line
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 15]
        if lines:
            return lines[0][:80]
        
        return "Job Opening (from LinkedIn Post)"
    
    def _extract_company_from_post(self, text: str, poster_name: str) -> str:
        """
        Extract company name from post text.
        """
        # Common patterns: "at Google", "@ Microsoft", "Company: XYZ"
        patterns = [
            r"(?:at|@|company[:\s])\s*([A-Z][A-Za-z\s&.]{2,40}?)(?:\.|,|\n|!|\s(?:is|are|we))",
            r"(?:join|joining)\s+([A-Z][A-Za-z\s&.]{2,40}?)(?:\.|,|\n|!|\s(?:as|for))",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                company = match.group(1).strip()
                if len(company) > 2:
                    return company[:60]
        
        # Use poster name as fallback
        return poster_name if poster_name != "Unknown Recruiter" else "Unknown Company"
    
    # Required by BaseCollector but not used (we override collect directly)
    async def search(self, page, query: str, location: str = ""):
        pass
    
    async def extract_listings(self, page) -> list[JobPosting]:
        return []
