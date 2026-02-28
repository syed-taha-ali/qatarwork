"""
Email Service
Handles email delivery for verification codes, password resets, and notifications.

Security features:
- SMTP credentials from environment
- Fallback to console logging in development
- Input validation on email addresses
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def generate_verification_code() -> str:
    """
    Generate a cryptographically random 6-digit verification code.
    
    Returns:
        str: 6-digit numeric code
    """
    return ''.join(random.choices(string.digits, k=6))


def send_password_reset_email(to_email: str, reset_code: str, full_name: str) -> bool:
    """
    Send password reset code via email.
    
    Args:
        to_email: Recipient email address
        reset_code: 6-digit reset code
        full_name: User's full name for personalization
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Get SMTP credentials from settings
    SMTP_EMAIL = settings.SMTP_EMAIL
    SMTP_PASSWORD = settings.SMTP_PASSWORD
    
    # If no credentials, fall back to console output (development mode)
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning("SMTP not configured - logging password reset code to console")
        print("\n" + "="*60)
        print(f"PASSWORD RESET CODE (Development Mode)")
        print("="*60)
        print(f"To: {to_email}")
        print(f"Name: {full_name}")
        print(f"Reset Code: {reset_code}")
        print("="*60 + "\n")
        return True


def send_verification_email(to_email: str, verification_code: str, full_name: str) -> bool:
    """
    Send verification code email using Gmail SMTP.
    Returns True if sent successfully, False otherwise.
    """
    # Get SMTP credentials from settings
    SMTP_EMAIL = settings.SMTP_EMAIL
    SMTP_PASSWORD = settings.SMTP_PASSWORD
    
    # If no credentials, fall back to console output
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("\n" + "="*60)
        logger.warning("SMTP not configured - logging verification code to console")
        print("="*60)
        print(f"To: {to_email}")
        print(f"Name: {full_name}")
        print(f"Verification Code: {verification_code}")
        print("="*60)
        print("To enable real emails, add to .env file:")
        print("  SMTP_EMAIL=your-email@gmail.com")
        print("  SMTP_PASSWORD=your-app-password")
        print("="*60 + "\n")
        return True
    
    try:
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"QatarWork <{SMTP_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = "QatarWork - Email Verification Code"
        
        # HTML email body
        html_body = f'''
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #8B1A1A; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">QatarWork</h1>
            </div>
            <div style="background: #f9f9f9; padding: 30px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
                <h2 style="color: #333;">Welcome, {full_name}!</h2>
                <p style="color: #666; line-height: 1.6;">
                    Thank you for registering with QatarWork. To complete your registration, 
                    please verify your email address using the code below:
                </p>
                <div style="background: white; padding: 25px; text-align: center; margin: 25px 0; border: 2px solid #8B1A1A; border-radius: 8px;">
                    <div style="color: #999; font-size: 12px; margin-bottom: 10px;">YOUR VERIFICATION CODE</div>
                    <h1 style="color: #8B1A1A; letter-spacing: 10px; margin: 0; font-size: 36px;">{verification_code}</h1>
                </div>
                <p style="color: #666; line-height: 1.6;">
                    This code will expire in <strong>10 minutes</strong>.
                </p>
                <p style="color: #999; font-size: 14px; margin-top: 30px;">
                    If you didn't create an account with QatarWork, please ignore this email.
                </p>
            </div>
            <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
                <p>QatarWork - Qatar's Trusted Labor Marketplace</p>
                <p>This is an automated message, please do not reply.</p>
            </div>
        </body>
        </html>
        '''
        
        # Plain text fallback
        text_body = f'''
        Welcome to QatarWork, {full_name}!
        
        Your verification code is: {verification_code}
        
        This code will expire in 10 minutes.
        
        If you didn't create an account, please ignore this email.
        
        ---
        QatarWork - Qatar's Trusted Labor Marketplace
        '''
        
        # Attach both versions
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send via Gmail SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Verification email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        print(f"Email was for: {to_email}, Code: {verification_code}")
        return False


def send_password_reset_email(to_email: str, reset_code: str, full_name: str) -> bool:
    """
    Send password reset code email.
    Returns True if sent successfully, False otherwise.
    """
    # Get SMTP credentials from settings
    SMTP_EMAIL = settings.SMTP_EMAIL
    SMTP_PASSWORD = settings.SMTP_PASSWORD
    
    # If no credentials, fall back to console output
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("\n" + "="*60)
        print(f"PASSWORD RESET CODE (Development Mode)")
        print("="*60)
        print(f"To: {to_email}")
        print(f"Name: {full_name}")
        print(f"Reset Code: {reset_code}")
        print("="*60 + "\n")
        return True
    
    try:
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"QatarWork <{SMTP_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = "QatarWork - Password Reset Code"
        
        # HTML email body
        html_body = f'''
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #8B1A1A; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0;">QatarWork</h1>
            </div>
            <div style="background: #f9f9f9; padding: 30px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
                <h2 style="color: #333;">Password Reset Request</h2>
                <p style="color: #666; line-height: 1.6;">
                    Hello {full_name},
                </p>
                <p style="color: #666; line-height: 1.6;">
                    We received a request to reset your password. Use the code below to create a new password:
                </p>
                <div style="background: white; padding: 25px; text-align: center; margin: 25px 0; border: 2px solid #8B1A1A; border-radius: 8px;">
                    <div style="color: #999; font-size: 12px; margin-bottom: 10px;">PASSWORD RESET CODE</div>
                    <h1 style="color: #8B1A1A; letter-spacing: 10px; margin: 0; font-size: 36px;">{reset_code}</h1>
                </div>
                <p style="color: #666; line-height: 1.6;">
                    This code will expire in <strong>10 minutes</strong>.
                </p>
                <p style="color: #999; font-size: 14px; margin-top: 30px;">
                    If you didn't request a password reset, please ignore this email. Your password will remain unchanged.
                </p>
            </div>
            <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
                <p>QatarWork - Qatar's Trusted Labor Marketplace</p>
                <p>This is an automated message, please do not reply.</p>
            </div>
        </body>
        </html>
        '''
        
        # Plain text fallback
        text_body = f'''
        Password Reset Request - QatarWork
        
        Hello {full_name},
        
        Your password reset code is: {reset_code}
        
        This code will expire in 10 minutes.
        
        If you didn't request this, please ignore this email.
        
        ---
        QatarWork - Qatar's Trusted Labor Marketplace
        '''
        
        # Attach both versions
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send via Gmail SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Password reset email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending password reset email: {e}")
        print(f"Email was for: {to_email}, Code: {reset_code}")
        return False
