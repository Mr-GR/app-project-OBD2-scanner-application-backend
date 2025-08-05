# api/utils/email.py
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import requests

logger = logging.getLogger(__name__)

class EmailService:
    """Email service for sending magic links"""
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_username)
        self.from_name = os.getenv("FROM_NAME", "OBD2 Scanner")
        
        # SendGrid API (alternative to SMTP)
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        
        # App configuration
        self.app_name = os.getenv("APP_NAME", "OBD2 Scanner")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8080")
    
    def send_magic_link(self, email: str, name: Optional[str], token: str) -> bool:
        """Send magic link email to user"""
        try:
            # Use custom scheme for deep linking to the app
            magic_link = f"obd2scanner://auth?token={token}"
            
            # Try SendGrid first, then fall back to SMTP
            if self.sendgrid_api_key:
                return self._send_via_sendgrid(email, name, magic_link)
            elif self.smtp_server and self.smtp_username and self.smtp_password:
                return self._send_via_smtp(email, name, magic_link)
            else:
                # Development mode - just log the magic link
                logger.warning("No email service configured. Magic link (DEV MODE):")
                logger.warning(f"Email: {email}")
                logger.warning(f"Magic Link: {magic_link}")
                return True
                
        except Exception as e:
            logger.error(f"Error sending magic link email: {e}")
            return False
    
    def _send_via_sendgrid(self, email: str, name: Optional[str], magic_link: str) -> bool:
        """Send email via SendGrid API"""
        try:
            url = "https://api.sendgrid.com/v3/mail/send"
            
            subject = f"Sign in to {self.app_name}"
            html_content = self._generate_html_email(name or "there", magic_link)
            text_content = self._generate_text_email(name or "there", magic_link)
            
            data = {
                "personalizations": [{
                    "to": [{"email": email, "name": name or ""}],
                    "subject": subject
                }],
                "from": {
                    "email": self.from_email,
                    "name": self.from_name
                },
                "content": [
                    {
                        "type": "text/plain",
                        "value": text_content
                    },
                    {
                        "type": "text/html",
                        "value": html_content
                    }
                ]
            }
            
            headers = {
                "Authorization": f"Bearer {self.sendgrid_api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            logger.info(f"SendGrid API response: {response.status_code}")
            logger.info(f"SendGrid response headers: {dict(response.headers)}")
            
            if response.status_code == 202:
                logger.info(f"Magic link email sent successfully to {email}")
                return True
            else:
                logger.error(f"SendGrid API error: {response.status_code} - {response.text}")
                logger.error(f"Request data: {data}")
                logger.error(f"Request headers: {headers}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending via SendGrid: {e}")
            return False
    
    def _send_via_smtp(self, email: str, name: Optional[str], magic_link: str) -> bool:
        """Send email via SMTP"""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Sign in to {self.app_name}"
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = email
            
            # Create text and HTML versions
            text_content = self._generate_text_email(name or "there", magic_link)
            html_content = self._generate_html_email(name or "there", magic_link)
            
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Magic link email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending via SMTP: {e}")
            return False
    
    def _generate_html_email(self, name: str, magic_link: str) -> str:
        """Generate HTML email content"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Sign in to {self.app_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .button {{ 
                    display: inline-block; 
                    padding: 12px 24px; 
                    background-color: #007bff; 
                    color: white; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    margin: 20px 0; 
                }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{self.app_name}</h1>
                </div>
                
                <h2>Hi {name}!</h2>
                
                <p>We received a request to sign in to your {self.app_name} account.</p>
                
                <p>Click the button below to sign in:</p>
                
                <p style="text-align: center;">
                    <a href="{magic_link}" class="button">Sign In</a>
                </p>
                
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; background: #f5f5f5; padding: 10px; border-radius: 3px;">
                    {magic_link}
                </p>
                
                <p><strong>This link will expire in 15 minutes.</strong></p>
                
                <p>If you didn't request this email, you can safely ignore it.</p>
                
                <div class="footer">
                    <p>This email was sent by {self.app_name}</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _generate_text_email(self, name: str, magic_link: str) -> str:
        """Generate plain text email content"""
        return f"""
Hi {name}!

We received a request to sign in to your {self.app_name} account.

Click this link to sign in:
{magic_link}

This link will expire in 15 minutes.

If you didn't request this email, you can safely ignore it.

---
{self.app_name}
        """.strip()

# Global email service instance
email_service = EmailService()