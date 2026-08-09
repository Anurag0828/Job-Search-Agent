# ============================================================
# Notification Agent — Builds and Sends the Daily Email Digest
# ============================================================
# PURPOSE:
#   Takes the final recommendations from the Ranking Agent and
#   transforms them into a beautiful HTML email, then sends it.
#
# WHAT THE EMAIL LOOKS LIKE:
#   ┌─────────────────────────────────────────────┐
#   │  Your Daily Job Matches — July 28, 2026     │
#   │  8 matches found from 347 jobs scanned      │
#   │                                             │
#   │  #1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
#   │  Senior Backend Engineer @ Google           │
#   │  Bangalore | Match: 92%                     │
#   │                                             │
#   │  WHY: Your Python + FastAPI experience      │
#   │  directly matches their requirements...     │
#   │                                             │
#   │  GAPS: Kubernetes, gRPC                     │
#   │  [View Job →]                               │
#   │                                             │
#   │  #2 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
#   │  ...                                        │
#   └─────────────────────────────────────────────┘
#
# DATA FLOW:
#   Ranking Agent → list[Recommendation] → NotificationAgent
#        │
#        ▼
#   Build HTML email body
#        │
#        ▼
#   EmailService.send()
#        │
#        ▼
#   User's inbox
# ============================================================

from datetime import datetime
from schemas.recommendation import Recommendation, DailyDigest
from services.email_service import EmailService


class NotificationAgent:
    """
    Builds the daily job digest email and sends it.
    
    Usage:
        agent = NotificationAgent()
        success = agent.send_digest(recommendations, stats)
    """

    def __init__(self):
        self.email_service = EmailService()

    # ================================================================
    # MAIN METHOD — Build and send the daily digest
    # ================================================================

    def send_digest(
        self,
        recommendations: list[Recommendation],
        total_jobs_scanned: int = 0,
        platforms_searched: list[str] = None,
        platforms_failed: list[str] = None,
    ) -> bool:
        """
        Build the HTML email and send it.
        
        Args:
            recommendations: Final ranked recommendations
            total_jobs_scanned: Total jobs collected today
            platforms_searched: Which platforms were searched
            platforms_failed: Which platforms had errors
        
        Returns:
            True if email sent successfully
        """
        if not recommendations:
            print("[Notification] No recommendations to send")
            return False

        print(f"\n[Notification] Building email with {len(recommendations)} recommendations...")

        # Build the DailyDigest data object
        digest = DailyDigest(
            recommendations=recommendations,
            total_jobs_scanned=total_jobs_scanned,
            platforms_searched=platforms_searched or [],
            platforms_failed=platforms_failed or [],
            generated_at=datetime.now(),
        )

        # Build the email subject
        today = datetime.now().strftime("%B %d, %Y")
        subject = f"Your Job Matches for {today} — {len(recommendations)} matches found"

        # Build the HTML email body
        html_body = self._build_html(digest)

        # Build plain text fallback
        plain_body = self._build_plain_text(digest)

        # Send the email
        success = self.email_service.send(
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
        )

        if success:
            print(f"[Notification] Email sent with {len(recommendations)} recommendations")
        else:
            print(f"[Notification] Failed to send email")

        return success

    # ================================================================
    # HTML EMAIL BUILDER — Creates a beautiful, responsive email
    # ================================================================

    def _build_html(self, digest: DailyDigest) -> str:
        """
        Build the full HTML email body.
        
        Groups jobs by platform (LinkedIn / Naukri / Indeed) into
        separate visually distinct sections.
        
        Email HTML must be INLINE-STYLED (no external CSS) because
        email clients strip <style> tags and external stylesheets.
        """
        recs = digest.recommendations
        today = datetime.now().strftime("%B %d, %Y")

        # Group recommendations by platform
        platform_groups = {}
        for rec in recs:
            platform_key = rec.platform or "other"
            if platform_key not in platform_groups:
                platform_groups[platform_key] = []
            platform_groups[platform_key].append(rec)

        # Platform display config: label, gradient colors, icon emoji
        platform_config = {
            "linkedin_jobs": {
                "label": "LinkedIn",
                "gradient": "linear-gradient(135deg, #0077B5, #00A0DC)",
                "icon": "🔗",
                "accent": "#0077B5",
            },
            "linkedin_posts": {
                "label": "LinkedIn Posts",
                "gradient": "linear-gradient(135deg, #0077B5, #00A0DC)",
                "icon": "📝",
                "accent": "#0077B5",
            },
            "naukri": {
                "label": "Naukri",
                "gradient": "linear-gradient(135deg, #4A25AA, #7B3FE4)",
                "icon": "💼",
                "accent": "#4A25AA",
            },
            "indeed": {
                "label": "Indeed",
                "gradient": "linear-gradient(135deg, #2164F3, #6693F5)",
                "icon": "🔍",
                "accent": "#2164F3",
            },
            "other": {
                "label": "Other Sources",
                "gradient": "linear-gradient(135deg, #374151, #6B7280)",
                "icon": "📋",
                "accent": "#374151",
            },
        }

        # Desired display order
        platform_order = ["linkedin_jobs", "linkedin_posts", "naukri", "indeed", "other"]

        # Build platform sections HTML
        platform_sections_html = ""
        for platform_key in platform_order:
            if platform_key not in platform_groups:
                continue
            group_recs = platform_groups[platform_key]
            config = platform_config.get(platform_key, platform_config["other"])
            platform_sections_html += self._build_platform_section(group_recs, config)

        # Also handle any unknown platforms
        for platform_key, group_recs in platform_groups.items():
            if platform_key not in platform_order:
                config = platform_config["other"].copy()
                config["label"] = platform_key.replace("_", " ").title()
                platform_sections_html += self._build_platform_section(group_recs, config)

        # Build the stats footer
        stats_html = self._build_stats_footer(digest)

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">

<!-- Main Container -->
<table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; width: 100%;">

    <!-- Header -->
    <tr><td style="background: linear-gradient(135deg, #1e40af, #3b82f6); border-radius: 12px 12px 0 0; padding: 32px 24px; text-align: center;">
        <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">
            Your Daily Job Matches
        </h1>
        <p style="margin: 8px 0 0; color: #bfdbfe; font-size: 14px;">
            {today} &bull; {len(recs)} matches from {digest.total_jobs_scanned} jobs scanned
        </p>
    </td></tr>

    <!-- Body -->
    <tr><td style="background-color: #ffffff; padding: 24px;">

        <!-- Summary Bar -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px; background-color: #eff6ff; border-radius: 8px; padding: 16px;">
        <tr>
            <td style="padding: 12px; text-align: center;">
                <span style="font-size: 28px; font-weight: 700; color: #1e40af;">{len(recs)}</span>
                <br><span style="font-size: 12px; color: #6b7280;">Matches</span>
            </td>
            <td style="padding: 12px; text-align: center;">
                <span style="font-size: 28px; font-weight: 700; color: #1e40af;">{digest.total_jobs_scanned}</span>
                <br><span style="font-size: 12px; color: #6b7280;">Jobs Scanned</span>
            </td>
            <td style="padding: 12px; text-align: center;">
                <span style="font-size: 28px; font-weight: 700; color: #1e40af;">{recs[0].match_score:.0f}%</span>
                <br><span style="font-size: 12px; color: #6b7280;">Top Match</span>
            </td>
        </tr>
        </table>

        <!-- Platform Sections -->
        {platform_sections_html}

    </td></tr>

    <!-- Footer -->
    <tr><td style="background-color: #f9fafb; border-radius: 0 0 12px 12px; padding: 20px 24px; border-top: 1px solid #e5e7eb;">
        {stats_html}
        <p style="margin: 12px 0 0; color: #9ca3af; font-size: 11px; text-align: center;">
            Powered by AI Job Search Agent &bull; Running on your machine
        </p>
    </td></tr>

</table>
</td></tr>
</table>

</body>
</html>
"""

    def _build_platform_section(self, recs: list, config: dict) -> str:
        """Build an HTML section for a single platform's jobs."""
        job_cards_html = ""
        for rec in recs:
            job_cards_html += self._build_job_card(rec, config["accent"])

        return f"""
        <!-- Platform Section: {config['label']} -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden;">
            <!-- Platform Header -->
            <tr><td style="background: {config['gradient']}; padding: 14px 20px;">
                <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td style="color: #ffffff; font-size: 16px; font-weight: 700;">
                        {config['icon']}  {config['label']}
                    </td>
                    <td style="text-align: right; color: rgba(255,255,255,0.85); font-size: 13px;">
                        {len(recs)} {'match' if len(recs) == 1 else 'matches'}
                    </td>
                </tr>
                </table>
            </td></tr>
            <!-- Platform Jobs -->
            <tr><td style="padding: 16px; background-color: #fafafa;">
                {job_cards_html}
            </td></tr>
        </table>
        """

    def _build_job_card(self, rec: Recommendation, accent_color: str = "#2563eb") -> str:
        """Build HTML for a single job recommendation card."""
        # Score color based on match quality
        if rec.match_score >= 85:
            score_color = "#059669"  # Green
            score_bg = "#d1fae5"
        elif rec.match_score >= 70:
            score_color = "#d97706"  # Amber
            score_bg = "#fef3c7"
        else:
            score_color = "#6b7280"  # Gray
            score_bg = "#f3f4f6"

        # Missing skills HTML
        missing_html = ""
        if rec.missing_skills:
            skills = ", ".join(rec.missing_skills[:5])  # Max 5 skills
            missing_html = f"""
            <p style="margin: 8px 0 0; font-size: 12px; color: #9ca3af;">
                <strong style="color: #6b7280;">Gaps:</strong> {skills}
            </p>
            """

        return f"""
        <!-- Job Card #{rec.rank_position} -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 12px; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; background-color: #ffffff;">
        <tr><td style="padding: 16px;">

            <!-- Title Row -->
            <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="vertical-align: top;">
                    <span style="font-size: 11px; color: #9ca3af;">#{rec.rank_position}</span>
                    <h3 style="margin: 4px 0; font-size: 16px; color: #111827;">{rec.title}</h3>
                    <p style="margin: 0; font-size: 14px; color: #4b5563;">
                        {rec.company or 'Unknown Company'}
                        {f' &bull; {rec.location}' if rec.location else ''}
                    </p>
                </td>
                <td style="vertical-align: top; text-align: right; width: 80px;">
                    <span style="display: inline-block; background-color: {score_bg}; color: {score_color}; font-weight: 700; font-size: 18px; padding: 8px 12px; border-radius: 8px;">
                        {rec.match_score:.0f}%
                    </span>
                </td>
            </tr>
            </table>

            <!-- Rationale -->
            <p style="margin: 12px 0 0; font-size: 13px; color: #4b5563; line-height: 1.5;">
                {rec.rationale}
            </p>

            {missing_html}

            <!-- Action Row -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 12px;">
            <tr>
                <td>
                    <a href="{rec.job_url}" style="display: inline-block; background-color: {accent_color}; color: #ffffff; text-decoration: none; padding: 8px 20px; border-radius: 6px; font-size: 13px; font-weight: 600;">
                        View Job
                    </a>
                </td>
            </tr>
            </table>

        </td></tr>
        </table>
        """

    def _build_stats_footer(self, digest: DailyDigest) -> str:
        """Build the email footer with run statistics."""
        searched = ", ".join(digest.platforms_searched) if digest.platforms_searched else "None"
        failed = ", ".join(digest.platforms_failed) if digest.platforms_failed else "None"

        return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 12px; color: #6b7280;">
        <tr>
            <td style="padding: 4px 0;">Platforms searched: <strong>{searched}</strong></td>
        </tr>
        {"<tr><td style='padding: 4px 0; color: #ef4444;'>Failed: <strong>" + failed + "</strong></td></tr>" if digest.platforms_failed else ""}
        </table>
        """

    # ================================================================
    # PLAIN TEXT BUILDER — Fallback for email clients without HTML
    # ================================================================

    def _build_plain_text(self, digest: DailyDigest) -> str:
        """Build plain text version of the email (grouped by platform)."""
        today = datetime.now().strftime("%B %d, %Y")
        lines = [
            f"Your Daily Job Matches — {today}",
            f"{len(digest.recommendations)} matches from {digest.total_jobs_scanned} jobs scanned",
            "",
            "=" * 50,
        ]

        # Group by platform
        platform_groups = {}
        for rec in digest.recommendations:
            key = rec.platform or "other"
            if key not in platform_groups:
                platform_groups[key] = []
            platform_groups[key].append(rec)

        platform_labels = {
            "linkedin_jobs": "LinkedIn",
            "linkedin_posts": "LinkedIn Posts",
            "naukri": "Naukri",
            "indeed": "Indeed",
        }

        for platform_key in ["linkedin_jobs", "linkedin_posts", "naukri", "indeed", "other"]:
            if platform_key not in platform_groups:
                continue
            group = platform_groups[platform_key]
            label = platform_labels.get(platform_key, platform_key.replace("_", " ").title())
            lines.append("")
            lines.append(f"━━━ {label} ({len(group)} matches) ━━━")
            lines.append("")

            for rec in group:
                lines.append(f"#{rec.rank_position} | {rec.match_score:.0f}% Match")
                lines.append(f"{rec.title} @ {rec.company or 'Unknown'}")
                if rec.location:
                    lines.append(f"Location: {rec.location}")
                lines.append(f"Why: {rec.rationale}")
                if rec.missing_skills:
                    lines.append(f"Gaps: {', '.join(rec.missing_skills)}")
                lines.append(f"Apply: {rec.job_url}")
                lines.append("-" * 50)

        # Handle unknown platforms
        for platform_key, group in platform_groups.items():
            if platform_key not in ["linkedin_jobs", "linkedin_posts", "naukri", "indeed", "other"]:
                lines.append("")
                lines.append(f"━━━ {platform_key.replace('_', ' ').title()} ({len(group)} matches) ━━━")
                for rec in group:
                    lines.append(f"#{rec.rank_position} | {rec.match_score:.0f}% Match")
                    lines.append(f"{rec.title} @ {rec.company or 'Unknown'}")
                    lines.append(f"Apply: {rec.job_url}")
                    lines.append("-" * 50)

        lines.append("")
        lines.append("Powered by AI Job Search Agent")
        return "\n".join(lines)
