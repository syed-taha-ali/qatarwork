"""
Application Configuration Module
Manages all application settings and environment variables.

This module provides centralized configuration management using Pydantic Settings.
All configuration values can be overridden via environment variables or .env file.

Security Note:
    - SECRET_KEY should be changed in production
    - Never commit .env file to version control
    - Use strong, random secrets in production
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings and configuration.
    
    All settings can be overridden via environment variables or .env file.
    
    Attributes:
        SECRET_KEY: Secret key for JWT token signing (MUST change in production)
        ALGORITHM: JWT hashing algorithm
        ACCESS_TOKEN_EXPIRE_MINUTES: JWT token expiration time
        DATABASE_URL: Database connection string
        PLATFORM_FEE_PERCENT: Platform fee percentage for transactions
        APP_NAME: Application display name
        DEBUG: Debug mode flag (disable in production)
        SMTP_EMAIL: SMTP email address for sending notifications
        SMTP_PASSWORD: SMTP password for email authentication
        WHAPI_API_KEY: WhatsApp API key for SMS/WhatsApp notifications
    """
    SECRET_KEY: str = "dev-secret-key-change-in-production-32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite:///./qatar_labor.db"
    PLATFORM_FEE_PERCENT: float = 10.0
    APP_NAME: str = "Qatar Skilled Labor Marketplace"
    DEBUG: bool = True
    
    # Email settings (optional - for notifications)
    SMTP_EMAIL: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    # WhatsApp settings (optional - for SMS/WhatsApp verification)
    WHAPI_API_KEY: Optional[str] = None

    class Config:
        """Pydantic configuration class."""
        env_file = ".env"


# Global settings instance
settings = Settings()
