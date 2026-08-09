# ============================================================
# Email Service — Sends Emails via Gmail SMTP
# ============================================================
# PURPOSE:
#   Sends the daily job digest email to the user.
#   Uses Gmail's SMTP server with an App Password.
#
# HOW IT WORKS:
#   1. Receives an HTML email body (from notification_agent)
#   2. Creates an email message with subject, sender, recipient
#   3. Connects to Gmail's SMTP server (smtp.gmail.com:587)
#   4. Authenticates with your App Password
#   5. Sends the email
#   6. Closes the connection
#
# SECURITY:
#   - Uses Gmail "App Password" (NOT your regular password)
#   - Connection is TLS-encrypted
#   - Credentials come from .env (never hardcoded)
#
# SETUP REQUIRED:
#   1. Enable 2-Step Verification on your Google account
#   2. Create an App Password at: myaccount.google.com
#   3. Add to .env:
#      EMAIL_SENDER=your.email@gmail.com
#      EMAIL_PASSWORD=yourapppassword
#      EMAIL_RECIPIENT=your.email@gmail.com
#
# USAGE:
#   from services.email_service import EmailService
#
#   email = EmailService()
#   email.send(
#       subject="Your Job Matches for July 28",
#       html_body="<h1>Today's Top Jobs</h1>..."
#   )
# ============================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import settings


class EmailService:
    """
    Sends emails using Gmail SMTP.
    
    Usage:
        service = EmailService()
        success = service.send(
            subject="Job Matches - July 28",
            html_body="<h1>Today's matches</h1><p>...</p>"
        )
    """

    def __init__(self):
        """
        Initialize the email service with settings from .env
        """
        self.sender = settings.EMAIL_SENDER
        self.password = settings.EMAIL_PASSWORD
        self.recipient = settings.EMAIL_RECIPIENT
        self.smtp_host = settings.EMAIL_SMTP_HOST
        self.smtp_port = settings.EMAIL_SMTP_PORT

    def send(self, subject: str, html_body: str, plain_body: str = "") -> bool:
        """
        Send an email with HTML content.
        
        Args:
            subject: Email subject line
            html_body: The HTML content of the email
            plain_body: Plain text fallback (for email clients that don't support HTML)
        
        Returns:
            True if sent successfully, False if failed
        
        HOW SMTP WORKS (simplified):
            1. Your app connects to smtp.gmail.com on port 587
            2. STARTTLS upgrades the connection to encrypted
            3. You authenticate with email + app password
            4. You send the message
            5. Gmail delivers it to the recipient's inbox
        """
        # Validate that email settings are configured
        if not self.sender or not self.password or not self.recipient:
            print("[Email] ERROR: Email settings not configured in .env")
            print("[Email] Required: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT")
            return False

        print(f"[Email] Sending email to: {self.recipient}")
        print(f"[Email] Subject: {subject}")

        try:
            # Step 1: Create the email message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"AI Job Search Agent <{self.sender}>"
            message["To"] = self.recipient

            # Add plain text version (fallback for older email clients)
            if plain_body:
                text_part = MIMEText(plain_body, "plain")
                message.attach(text_part)

            # Add HTML version (the rich email)
            html_part = MIMEText(html_body, "html")
            message.attach(html_part)

            # Step 2: Connect to Gmail SMTP server
            print(f"[Email] Connecting to {self.smtp_host}:{self.smtp_port}...")
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)

            # Step 3: Upgrade to encrypted connection
            server.starttls()

            # Step 4: Authenticate
            server.login(self.sender, self.password)

            # Step 5: Send the email
            server.sendmail(self.sender, self.recipient, message.as_string())
            print(f"[Email] Sent successfully!")

            # Step 6: Close the connection
            server.quit()
            return True

        except smtplib.SMTPAuthenticationError:
            print(f"[Email] Authentication failed!")
            print(f"[Email] Make sure you're using a Gmail App Password, NOT your regular password.")
            print(f"[Email] Create one at: myaccount.google.com > Security > App Passwords")
            return False
        except Exception as e:
            print(f"[Email] Failed to send: {str(e)}")
            return False

    def send_test(self) -> bool:
        """
        Send a test email to verify the configuration works.
        
        Usage:
            service = EmailService()
            if service.send_test():
                print("Email works!")
            else:
                print("Check your settings")
        """
        return self.send(
            subject="[Test] AI Job Search Agent - Email Works!",
            html_body="""
            <div style="font-family: Arial; padding: 20px; max-width: 600px; margin: auto;">
                <h2 style="color: #2563eb;">Email Configuration Successful!</h2>
                <p>Your AI Job Search Agent can now send daily digests to this email address.</p>
                <hr style="border: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 12px;">
                    This is a test email from your AI Job Search Agent.
                </p>
            </div>
            """,
            plain_body="Email configuration successful! Your AI Job Search Agent can now send daily digests.",
        )
