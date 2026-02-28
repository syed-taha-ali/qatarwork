"""
Admin Routes
Administrative functions for verification management and platform oversight.

This module handles:
- Verification application reviews
- User document access (secure)
- Admin approval/rejection workflows
"""
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from pathlib import Path
import logging

from app.database import get_db
from app.models.models import User, UserRole
from app.services.auth_service import get_current_user
from app.services.document_service import get_user_documents, get_document_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="app/templates")


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure user has admin privileges.
    
    Args:
        current_user: Authenticated user from get_current_user dependency
    
    Returns:
        User object if admin
        
    Raises:
        HTTPException: 403 if user is not an admin
    """
    if current_user.role != UserRole.admin:
        logger.warning(f"Non-admin user {current_user.id} attempted admin access")
        raise HTTPException(403, "Admin access required")
    return current_user


@router.get("/verifications", response_class=HTMLResponse)
async def verifications_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List pending verifications."""
    pending = db.query(User).filter(User.verification_status == "pending").order_by(User.verification_applied_at.desc()).all()
    reviewed = db.query(User).filter(User.verification_status.in_(["approved", "rejected"])).order_by(User.verification_reviewed_at.desc()).limit(10).all()
    
    return templates.TemplateResponse("admin/verifications.html", {
        "request": request,
        "current_user": admin,
        "pending_users": pending,
        "reviewed_users": reviewed
    })


@router.get("/verifications/{user_id}", response_class=HTMLResponse)
async def review_verification(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Review a user's verification application."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    documents = get_user_documents(user.id)
    
    return templates.TemplateResponse("admin/review_verification.html", {
        "request": request,
        "current_user": admin,
        "user": user,
        "documents": documents
    })


@router.post("/verifications/{user_id}/approve")
async def approve_verification(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Approve verification, delete documents, and log to history."""
    from app.services.document_service import delete_all_user_documents
    from app.models.models import VerificationHistory
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    user.verification_status = "approved"
    user.verification_reviewed_at = datetime.utcnow()
    user.verification_reviewed_by = admin.id
    user.verification_rejection_reason = None
    
    # Log to history
    history_entry = VerificationHistory(
        user_id=user_id,
        applied_at=user.verification_applied_at or datetime.utcnow(),
        status="approved",
        reviewed_at=datetime.utcnow(),
        reviewed_by_id=admin.id
    )
    db.add(history_entry)
    db.commit()
    
    # Delete all sensitive documents after approval
    deleted_count = delete_all_user_documents(user_id)
    logger.info(f"Verification approved: user_id={user_id}, admin_id={admin.id}, documents_deleted={deleted_count}")
    
    return RedirectResponse("/admin/verifications?success=Application approved and documents deleted", status_code=302)


@router.post("/verifications/{user_id}/reject")
async def reject_verification(
    user_id: int,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Reject verification, delete documents, and log to history."""
    from app.models.models import VerificationHistory
    from app.services.document_service import delete_all_user_documents
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    user.verification_status = "rejected"
    user.verification_reviewed_at = datetime.utcnow()
    user.verification_reviewed_by = admin.id
    user.verification_rejection_reason = reason
    
    # Log to history
    history_entry = VerificationHistory(
        user_id=user_id,
        applied_at=user.verification_applied_at or datetime.utcnow(),
        status="rejected",
        reviewed_at=datetime.utcnow(),
        reviewed_by_id=admin.id,
        rejection_reason=reason
    )
    db.add(history_entry)
    db.commit()
    
    # Delete all sensitive documents after rejection
    deleted_count = delete_all_user_documents(user_id)
    logger.info(f"Verification rejected: user_id={user_id}, admin_id={admin.id}, reason={reason[:50]}, documents_deleted={deleted_count}")
    
    return RedirectResponse("/admin/verifications?success=Application rejected and documents deleted", status_code=302)


@router.get("/documents/{user_id}/{filename}")
async def view_document(
    user_id: int,
    filename: str,
    admin: User = Depends(require_admin)
):
    """View a user's document (admin only)."""
    filepath = get_document_path(user_id, filename)
    if not filepath:
        raise HTTPException(404, "Document not found")
    
    return FileResponse(filepath)
