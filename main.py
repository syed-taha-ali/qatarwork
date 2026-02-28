"""
Qatar Labor Platform - Main Application
A secure marketplace connecting skilled laborers with clients in Qatar.

Security Features:
- End-to-end encrypted messaging
- Rate limiting on all endpoints
- Security headers (HSTS, CSP, X-Frame-Options)
- Input validation and sanitization
- Secure session management
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

from app.config import settings
from app.database import engine, Base
from app.models import models  # Ensure all models are registered
from app.routers import auth, workers, jobs, bookings, pages, chats, profile, verification, admin
from app.middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware, RequestValidationMiddleware
from app.logging_config import setup_logging

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting Qatar Labor Platform...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    yield
    # Shutdown
    logger.info("Shutting down Qatar Labor Platform...")


app = FastAPI(
    title=settings.APP_NAME,
    description="A secure marketplace connecting skilled laborers in Qatar with clients seeking temporary services.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Security Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestValidationMiddleware)

logger.info("Security middleware initialized")

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(workers.router)
app.include_router(jobs.router)
app.include_router(bookings.router)
app.include_router(chats.router)
app.include_router(profile.router)
app.include_router(verification.router)
app.include_router(admin.router)


# --- Global exception handler for 404 ----------------------------------------
@app.exception_handler(404)
async def not_found(request: Request, exc):
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)


# --- Global exception handler for 401 Unauthorized ---------------------------
@app.exception_handler(401)
async def unauthorized(request: Request, exc: HTTPException):
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("errors/401.html", {"request": request}, status_code=401)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
