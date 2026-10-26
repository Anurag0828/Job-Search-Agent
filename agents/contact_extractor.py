# ============================================================
# Contact Extractor Agent — Extracts HR Emails & Apply Methods
# ============================================================
# PURPOSE:
#   Scans job descriptions and LinkedIn post texts to extract:
#   1. HR email addresses (careers@company.com, hr@xyz.com)
#   2. Application methods ("DM me", "Apply at portal.com", etc.)
#   3. Recruiter names and contact details
#
# WHY THIS MATTERS:
#   Many job posts (especially LinkedIn posts) say things like
#   "Interested? Email your resume to hr@company.com" or
#   "DM me on LinkedIn". This agent extracts that info so
#   the email digest can tell you EXACTLY how to apply.
#
# DATA FLOW:
#   Job description text → ContactExtractor.extract()
#       → { hr_email, application_method, recruiter_name }
#       → Stored in job_postings table (new columns)
#       → Displayed in email digest
# ============================================================

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class ContactInfo:
    """Extracted contact/application information from a job posting."""
    hr_email: Optional[str] = None
    application_method: Optional[str] = None  # "Email", "DM", "Portal", "Easy Apply"
    application_url: Optional[str] = None     # Direct apply link if found
    recruiter_name: Optional[str] = None
    is_urgent: bool = False                   # "URGENT", "ASAP", "Immediate joining"


# ============================================================
# PATTERNS — Regex patterns for extraction
# ============================================================

# Email addresses (excluding common false positives)
EMAIL_PATTERN = re.compile(
    r'[\w.+-]+@[\w-]+\.[\w.-]+',
    re.IGNORECASE
)
EMAIL_EXCLUDE = re.compile(
    r'(example\.com|test\.com|placeholder|noreply|no-reply|unsubscribe)',
    re.IGNORECASE
)

# Application method signals
DM_SIGNALS = re.compile(
    r'(dm\s+me|message\s+me|reach\s+out|send\s+me\s+a\s+message|'
    r'drop\s+me\s+a\s+message|inbox\s+me|connect\s+with\s+me|'
    r'ping\s+me|text\s+me|contact\s+me)',
    re.IGNORECASE
)

PORTAL_SIGNALS = re.compile(
    r'(apply\s+(?:at|on|via|through|here)\s*[:\s]*(?:https?://[\w./\-?=&]+))',
    re.IGNORECASE
)

URL_PATTERN = re.compile(
    r'https?://[\w./\-?=&%#]+',
    re.IGNORECASE
)

SEND_RESUME_SIGNALS = re.compile(
    r'(send\s+(?:your\s+)?(?:resume|cv|profile)\s+(?:to|at)\s+[\w.+-]+@[\w-]+\.[\w.-]+|'
    r'email\s+(?:your\s+)?(?:resume|cv|profile)\s+(?:to|at)\s+[\w.+-]+@[\w-]+\.[\w.-]+|'
    r'forward\s+(?:your\s+)?(?:resume|cv)\s+(?:to|at)\s+[\w.+-]+@[\w-]+\.[\w.-]+)',
    re.IGNORECASE
)

URGENCY_SIGNALS = re.compile(
    r'(urgent|asap|immediate\s+join|immediately|'
    r'urgent\s+hiring|urgent\s+requirement|'
    r'walk.?in|walk\s+in\s+interview)',
    re.IGNORECASE
)

# Posted time patterns for recency calculation
POSTED_TIME_PATTERNS = [
    (re.compile(r'(\d+)\s*(?:minute|min)s?\s*ago', re.IGNORECASE), 'minutes'),
    (re.compile(r'(\d+)\s*(?:hour|hr)s?\s*ago', re.IGNORECASE), 'hours'),
    (re.compile(r'(\d+)\s*(?:day)s?\s*ago', re.IGNORECASE), 'days'),
    (re.compile(r'(\d+)\s*(?:week)s?\s*ago', re.IGNORECASE), 'weeks'),
    (re.compile(r'(\d+)\s*(?:month)s?\s*ago', re.IGNORECASE), 'months'),
    (re.compile(r'just\s*(?:now|posted)', re.IGNORECASE), 'just_now'),
    (re.compile(r'today', re.IGNORECASE), 'today'),
    (re.compile(r'yesterday', re.IGNORECASE), 'yesterday'),
]


class ContactExtractor:
    """
    Extracts HR contact info and application methods from job descriptions.
    
    Usage:
        extractor = ContactExtractor()
        info = extractor.extract("Send resume to hr@google.com or DM me")
        print(info.hr_email)            # "hr@google.com"
        print(info.application_method)  # "Email resume to hr@google.com"
    """
    
    def extract(self, text: str, poster_name: str = None) -> ContactInfo:
        """
        Extract contact info from a job description or post text.
        
        Args:
            text: The full job description or LinkedIn post text
            poster_name: Name of the person who posted (for DM instructions)
            
        Returns:
            ContactInfo with extracted email, application method, etc.
        """
        if not text:
            return ContactInfo()
        
        info = ContactInfo()
        
        # 1. Extract HR email
        info.hr_email = self._extract_email(text)
        
        # 2. Determine application method
        info.application_method = self._determine_apply_method(text, info.hr_email, poster_name)
        
        # 3. Extract apply URL
        info.application_url = self._extract_apply_url(text)
        
        # 4. Check urgency
        info.is_urgent = bool(URGENCY_SIGNALS.search(text))
        
        # 5. Set recruiter name
        info.recruiter_name = poster_name
        
        return info
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract the most relevant HR/recruiter email from text."""
        emails = EMAIL_PATTERN.findall(text)
        
        # Filter out obviously non-HR emails
        valid_emails = [
            e for e in emails
            if not EMAIL_EXCLUDE.search(e)
        ]
        
        if not valid_emails:
            return None
        
        # Prioritize HR-looking emails
        hr_keywords = ['hr', 'career', 'recruit', 'talent', 'hiring', 'jobs', 'apply']
        for email in valid_emails:
            if any(kw in email.lower() for kw in hr_keywords):
                return email
        
        # Return the first valid email
        return valid_emails[0]
    
    def _determine_apply_method(self, text: str, email: Optional[str], poster_name: Optional[str]) -> str:
        """Determine how the user should apply to this job."""
        
        # Check for explicit "send resume to email" instructions
        if SEND_RESUME_SIGNALS.search(text) and email:
            return f"Email resume to {email}"
        
        # Check for DM signals
        if DM_SIGNALS.search(text):
            if poster_name:
                return f"DM {poster_name} on LinkedIn"
            return "DM the recruiter on LinkedIn"
        
        # Check for portal/URL
        if PORTAL_SIGNALS.search(text):
            return "Apply via company portal"
        
        # If email was found but no explicit instruction
        if email:
            return f"Send resume to {email}"
        
        # Default
        return "Apply via job link"
    
    def _extract_apply_url(self, text: str) -> Optional[str]:
        """Extract application URL if present."""
        urls = URL_PATTERN.findall(text)
        
        # Filter for apply-related URLs
        apply_keywords = ['apply', 'career', 'jobs', 'hiring', 'form', 'application']
        for url in urls:
            if any(kw in url.lower() for kw in apply_keywords):
                return url
        
        return urls[0] if urls else None
    
    @staticmethod
    def parse_posted_hours_ago(posted_date_str: str) -> Optional[int]:
        """
        Convert a human-readable posted date to hours ago.
        
        Examples:
            "2 hours ago" → 2
            "1 day ago" → 24
            "3 days ago" → 72
            "just now" → 0
            "1 week ago" → 168
        
        Returns:
            Number of hours ago, or None if unparseable.
        """
        if not posted_date_str:
            return None
        
        for pattern, unit in POSTED_TIME_PATTERNS:
            match = pattern.search(posted_date_str)
            if match:
                if unit == 'just_now':
                    return 0
                elif unit == 'today':
                    return 1
                elif unit == 'yesterday':
                    return 24
                else:
                    value = int(match.group(1))
                    multipliers = {
                        'minutes': 1/60,
                        'hours': 1,
                        'days': 24,
                        'weeks': 168,
                        'months': 720,
                    }
                    return int(value * multipliers.get(unit, 24))
        
        return None


# Singleton
_extractor_instance: Optional[ContactExtractor] = None

def get_contact_extractor() -> ContactExtractor:
    """Get or create the global ContactExtractor instance."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = ContactExtractor()
    return _extractor_instance
