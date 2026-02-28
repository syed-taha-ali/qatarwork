from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import shutil
from pathlib import Path

from app.database import get_db
from app.models.models import User, WorkerProfile, UserRole
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/profile", tags=["Profile"])
templates = Jinja2Templates(directory="app/templates")

# Upload directory
UPLOAD_DIR = Path("app/static/uploads/profiles")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def save_profile_picture(file: UploadFile, user_id: int) -> str:
    """Save uploaded profile picture and return the path."""
    if not file or not file.filename:
        return None
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Only image files are allowed")
    
    # Validate file size (5MB max)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(400, "File size must be less than 5MB")
    
    # Generate filename
    ext = file.filename.split(".")[-1].lower()
    filename = f"user_{user_id}.{ext}"
    filepath = UPLOAD_DIR / filename
    
    # Save file
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return f"/static/uploads/profiles/{filename}"


@router.get("/edit", response_class=HTMLResponse)
async def edit_profile_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Show profile edit form."""
    from app.services.document_service import get_user_documents
    
    # Get user's documents
    documents = get_user_documents(current_user.id)
    
    return templates.TemplateResponse("profile/edit.html", {
        "request": request,
        "current_user": current_user,
        "documents": documents
    })


@router.post("/edit")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(...),
    profile_picture: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user profile information."""
    # Check if email is taken by another user
    existing_user = db.query(User).filter(
        User.email == email,
        User.id != current_user.id
    ).first()
    
    if existing_user:
        return templates.TemplateResponse("profile/edit.html", {
            "request": request,
            "current_user": current_user,
            "error": "Email already in use by another account"
        })
    
    # Update user fields
    current_user.full_name = full_name
    current_user.email = email
    current_user.phone = phone if phone else None
    
    # Handle profile picture upload
    if profile_picture and profile_picture.filename:
        try:
            picture_path = await save_profile_picture(profile_picture, current_user.id)
            current_user.profile_picture = picture_path
        except HTTPException as e:
            return templates.TemplateResponse("profile/edit.html", {
                "request": request,
                "current_user": current_user,
                "error": str(e.detail)
            })
    
    db.commit()
    db.refresh(current_user)
    
    return RedirectResponse("/profile/edit?success=Profile updated successfully!", status_code=302)


@router.post("/worker/edit")
async def update_worker_profile(
    request: Request,
    hourly_rate: float = Form(...),
    bio: str = Form(""),
    location: str = Form(""),
    years_experience: int = Form(0),
    is_available: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update worker-specific profile information."""
    if current_user.role != UserRole.worker:
        raise HTTPException(status_code=403, detail="Only workers can update worker profile")
    
    profile = current_user.worker_profile
    if not profile:
        raise HTTPException(status_code=404, detail="Worker profile not found")
    
    # Validate hourly rate
    if hourly_rate <= 0:
        return templates.TemplateResponse("profile/edit.html", {
            "request": request,
            "current_user": current_user,
            "error": "Hourly rate must be positive"
        })
    
    # Update worker profile
    profile.hourly_rate = hourly_rate
    profile.bio = bio if bio else None
    profile.location = location if location else None
    profile.years_experience = years_experience
    profile.is_available = is_available
    
    db.commit()
    db.refresh(current_user)
    
    return RedirectResponse("/profile/edit?success=Worker profile updated successfully!", status_code=302)


# --- Document Upload Routes --------------------------------------------------

@router.post("/documents/qid")
async def upload_qid_documents(
    request: Request,
    qid_front: UploadFile = File(None),
    qid_back: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload QID front and back documents."""
    from app.services.document_service import save_qid_document
    
    try:
        uploaded = []
        
        # Upload front
        if qid_front and qid_front.filename:
            filename = await save_qid_document(current_user.id, qid_front, "front")
            uploaded.append(f"Front: {filename}")
        
        # Upload back
        if qid_back and qid_back.filename:
            filename = await save_qid_document(current_user.id, qid_back, "back")
            uploaded.append(f"Back: {filename}")
        
        if not uploaded:
            return RedirectResponse(
                "/profile/edit?error=No files selected",
                status_code=302
            )
        
        success_msg = "QID documents uploaded: " + ", ".join(uploaded)
        return RedirectResponse(
            f"/profile/edit?success={success_msg}",
            status_code=302
        )
        
    except HTTPException as e:
        return RedirectResponse(
            f"/profile/edit?error={e.detail}",
            status_code=302
        )
    except Exception as e:
        print(f"Error uploading QID: {e}")
        return RedirectResponse(
            f"/profile/edit?error=Failed to upload documents",
            status_code=302
        )


@router.post("/documents/credentials")
async def upload_credential_documents(
    request: Request,
    credential_1: UploadFile = File(None),
    credential_2: UploadFile = File(None),
    credential_3: UploadFile = File(None),
    credential_4: UploadFile = File(None),
    credential_5: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload credential documents (workers only)."""
    from app.services.document_service import save_credential_document
    
    # Verify user is a worker
    if current_user.role != UserRole.worker:
        return RedirectResponse(
            "/profile/edit?error=Only workers can upload credentials",
            status_code=302
        )
    
    try:
        uploaded = []
        credentials = [credential_1, credential_2, credential_3, credential_4, credential_5]
        
        for i, cred_file in enumerate(credentials, start=1):
            if cred_file and cred_file.filename:
                filename = await save_credential_document(current_user.id, cred_file, i)
                uploaded.append(f"Document {i}")
        
        if not uploaded:
            return RedirectResponse(
                "/profile/edit?error=No files selected",
                status_code=302
            )
        
        success_msg = "Credentials uploaded: " + ", ".join(uploaded)
        return RedirectResponse(
            f"/profile/edit?success={success_msg}",
            status_code=302
        )
        
    except HTTPException as e:
        return RedirectResponse(
            f"/profile/edit?error={e.detail}",
            status_code=302
        )
    except Exception as e:
        print(f"Error uploading credentials: {e}")
        return RedirectResponse(
            f"/profile/edit?error=Failed to upload documents",
            status_code=302
        )
