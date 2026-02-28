"""
Security Middleware
Implements security best practices including rate limiting and security headers.
"""
from fastapi import Request, HTTPException
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all HTTP responses.
    
    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: HSTS for HTTPS
    - Content-Security-Policy: Basic CSP
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HSTS (only for HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Basic CSP
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://cdnjs.cloudflare.com; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting middleware.
    
    Limits:
    - 100 requests per minute per IP for general endpoints
    - 5 requests per minute per IP for auth endpoints
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.request_counts = defaultdict(list)
        self.general_limit = 100  # requests per minute
        self.auth_limit = 10  # requests per minute for auth endpoints (increased from 5)
    
    def _clean_old_requests(self, ip: str, now: datetime):
        """Remove requests older than 1 minute."""
        cutoff = now - timedelta(minutes=1)
        self.request_counts[ip] = [
            req_time for req_time in self.request_counts[ip]
            if req_time > cutoff
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host
        now = datetime.utcnow()
        
        # Clean old requests
        self._clean_old_requests(client_ip, now)
        
        # Determine limit based on endpoint
        path = request.url.path
        limit = self.auth_limit if path.startswith("/auth/") else self.general_limit
        
        # Check rate limit
        if len(self.request_counts[client_ip]) >= limit:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}, path: {path}")
            # Return 429 response instead of raising HTTPException
            return Response(
                content="Too many requests. Please try again later.",
                status_code=429,
                headers={"Retry-After": "60"}
            )
        
        # Record this request
        self.request_counts[client_ip].append(now)
        
        return await call_next(request)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Validates and sanitizes incoming requests.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Check request size (prevent large payload attacks)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
            logger.warning(f"Request too large: {content_length} bytes from {request.client.host}")
            return Response(
                content="Request entity too large",
                status_code=413
            )
        
        return await call_next(request)
