from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.models import User, UserRole
from app.services.auth_service import get_current_user
from app.services.document_service import get_user_documents

router = APIRouter(prefix="/verification", tags=["Verification"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/apply", response_class=HTMLResponse)
async def verification_application_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Show verification application page."""
    # Get user's documents
    documents = get_user_documents(current_user.id)
    
    return templates.TemplateResponse("verification/apply.html", {
        "request": request,
        "current_user": current_user,
        "documents": documents
    })


@router.post("/apply")
async def submit_verification_application(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit verification application and log to history."""
    from app.services.document_service import get_user_documents
    from app.models.models import VerificationHistory
    
    # Validate requirements
    documents = get_user_documents(current_user.id)
    
    if not current_user.profile_picture:
        return RedirectResponse(
            "/verification/apply?error=Profile picture required",
            status_code=302
        )
    
    if not documents.get("qid_front") or not documents.get("qid_back"):
        return RedirectResponse(
            "/verification/apply?error=QID front and back required",
            status_code=302
        )
    
    # Worker-specific validation
    if current_user.role == UserRole.worker:
        if not current_user.worker_profile or not current_user.worker_profile.bio:
            return RedirectResponse(
                "/verification/apply?error=Complete profile required (bio, location, experience)",
                status_code=302
            )
    
    # Update verification status
    current_user.verification_status = "pending"
    current_user.verification_applied_at = datetime.utcnow()
    current_user.verification_rejection_reason = None  # Clear previous rejection
    
    # Log to history
    history_entry = VerificationHistory(
        user_id=current_user.id,
        applied_at=datetime.utcnow(),
        status="submitted"
    )
    db.add(history_entry)
    db.commit()
    
    return RedirectResponse(
        "/verification/apply?success=Application submitted! You'll be notified once reviewed.",
        status_code=302
    )
