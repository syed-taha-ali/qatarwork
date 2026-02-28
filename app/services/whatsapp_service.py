"""
WhatsApp service for sending OTP verification codes via Whapi.cloud
"""
import requests
import logging
import random
import string
from app.config import settings

logger = logging.getLogger(__name__)


def generate_otp_code() -> str:
    """Generate a 6-digit OTP code."""
    return ''.join(random.choices(string.digits, k=6))


def send_whatsapp_otp(phone_number: str, otp_code: str, full_name: str) -> bool:
    """
    Send OTP code via WhatsApp using Whapi.cloud API.
    
    Args:
        phone_number: Phone number in international format (e.g., +97450001234)
        otp_code: 6-digit OTP code
        full_name: User's full name
    
    Returns:
        True if sent successfully, False otherwise
    """
    # Get WhatsApp API credentials from settings
    API_KEY = settings.WHAPI_API_KEY
    
    # If no credentials, fall back to console output
    if not API_KEY:
        print("\n" + "="*60)
        logger.warning("WhatsApp not configured - logging OTP code to console")
        print("="*60)
        print(f"To: {phone_number}")
        print(f"Name: {full_name}")
        print(f"OTP Code: {otp_code}")
        print("="*60)
        print("To enable WhatsApp OTP, add to .env file:")
        print("  WHAPI_API_KEY=your-whapi-api-key")
        print("="*60 + "\n")
        return True
    
    try:
        # Format phone number for Whapi.cloud
        # Remove all non-digit characters except +
        clean_phone = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        
        # Remove leading + if present
        if clean_phone.startswith('+'):
            clean_phone = clean_phone[1:]
        
        # Whapi.cloud format: {phone}@s.whatsapp.net
        whatsapp_id = f"{clean_phone}@s.whatsapp.net"
        
        # Whapi.cloud API endpoint
        url = "https://gate.whapi.cloud/messages/text"
        
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {API_KEY}",
            "content-type": "application/json"
        }
        
        # Message body with formatting
        message = f"""🔐 *QatarWork Verification*

Hello {full_name}!

Your phone verification code is:

*{otp_code}*

This code will expire in 5 minutes.

If you didn't request this code, please ignore this message.

---
_QatarWork - Qatar's Trusted Labor Marketplace_"""
        
        payload = {
            "typing_time": 0,
            "to": whatsapp_id,
            "body": message
        }
        
        # Send request to Whapi.cloud
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"WhatsApp OTP sent to {phone_number}")
            return True
        else:
            logger.error(f"WhatsApp API error: {response.status_code}")
            print(f"Response: {response.text}")
            print(f"Console fallback - Code: {otp_code}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"WhatsApp API timeout for {phone_number}")
        print(f"Console fallback - Code: {otp_code}")
        return False
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp OTP: {e}")
        print(f"Phone: {phone_number}, Code: {otp_code}")
        return False


def format_phone_number(phone: str) -> str:
    """
    Format phone number to international format.
    Assumes Qatar numbers if no country code provided.
    
    Args:
        phone: Raw phone number input
    
    Returns:
        Formatted international phone number
    """
    # Remove all non-digit characters except +
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # If starts with +, return as is
    if clean.startswith('+'):
        return clean
    
    # If starts with 974 (Qatar code), add +
    if clean.startswith('974'):
        return '+' + clean
    
    # If starts with 0, remove it and add +974 (Qatar)
    if clean.startswith('0'):
        return '+974' + clean[1:]
    
    # Otherwise assume Qatar number, add +974
    if len(clean) == 8:  # Qatar mobile numbers are 8 digits
        return '+974' + clean
    
    # Return with + if doesn't have it
    return '+' + clean if not clean.startswith('+') else clean
