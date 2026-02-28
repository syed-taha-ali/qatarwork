from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from app.database import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import UserCreate, Token
from app.services.auth_service import (
    hash_password, verify_password,
    create_access_token, get_current_user_optional
)
from app.services.email_service import generate_verification_code, send_verification_email, send_password_reset_email
from app.services.whatsapp_service import generate_otp_code, send_whatsapp_otp, format_phone_number

router = APIRouter(prefix="/auth", tags=["Authentication"])
templates = Jinja2Templates(directory="app/templates")

# Temporary storage for pending registrations (in production, use Redis or database)
pending_registrations = {}

# Temporary storage for password resets
password_reset_tokens = {}

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
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
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


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
async def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: str = Form(""),
    role: str = Form(...),
    profile_picture: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Validate role
    if role not in [r.value for r in UserRole]:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "error": "Invalid role selected."
        })

    # Check duplicate email
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "error": "Email already registered."
        })

    if len(password) < 6:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, "error": "Password must be at least 6 characters."
        })

    # Generate verification code
    verification_code = generate_verification_code()
    
    # Save profile picture file data if provided
    profile_pic_data = None
    profile_pic_filename = None
    if profile_picture and profile_picture.filename:
        # Read file into memory
        profile_pic_data = await profile_picture.read()
        profile_pic_filename = profile_picture.filename
        # Reset file pointer
        await profile_picture.seek(0)
    
    # Store registration data temporarily (expires in 10 minutes)
    registration_key = email.lower()
    pending_registrations[registration_key] = {
        "full_name": full_name,
        "email": email,
        "password_hash": hash_password(password),
        "phone": phone if phone else None,
        "role": role,
        "profile_picture_data": profile_pic_data,
        "profile_picture_filename": profile_pic_filename,
        "verification_code": verification_code,
        "expires_at": datetime.utcnow() + timedelta(minutes=10)
    }
    
    # Send verification email
    email_sent = send_verification_email(email, verification_code, full_name)
    
    if not email_sent:
        return templates.TemplateResponse("auth/register.html", {
            "request": request, 
            "error": "Failed to send verification email. Please try again."
        })
    
    # Redirect to verification page
    return RedirectResponse(f"/auth/verify?email={email}", status_code=302)


@router.get("/verify", response_class=HTMLResponse)
async def verify_page(
    request: Request,
    email: str,
    db: Session = Depends(get_db)
):
    """Show email verification page."""
    user = await get_current_user_optional(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    
    return templates.TemplateResponse("auth/verify.html", {
        "request": request,
        "email": email
    })


@router.post("/verify")
async def verify_email(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verify email code and create user account."""
    registration_key = email.lower()
    
    # Check if pending registration exists
    if registration_key not in pending_registrations:
        return templates.TemplateResponse("auth/verify.html", {
            "request": request,
            "email": email,
            "error": "Registration expired or not found. Please register again."
        })
    
    pending = pending_registrations[registration_key]
    
    # Check if expired
    if datetime.utcnow() > pending["expires_at"]:
        del pending_registrations[registration_key]
        return templates.TemplateResponse("auth/verify.html", {
            "request": request,
            "email": email,
            "error": "Verification code expired. Please register again."
        })
    
    # Verify code
    if code != pending["verification_code"]:
        return templates.TemplateResponse("auth/verify.html", {
            "request": request,
            "email": email,
            "error": "Invalid verification code. Please try again."
        })
    
    # Code is correct - mark email as verified
    pending["email_verified"] = True
    
    # Now send phone OTP
    if not pending["phone"]:
        return templates.TemplateResponse("auth/verify.html", {
            "request": request,
            "email": email,
            "error": "Phone number is required. Please register again."
        })
    
    # Generate phone OTP
    phone_otp = generate_otp_code()
    pending["phone_otp_code"] = phone_otp
    pending["expires_at"] = datetime.utcnow() + timedelta(minutes=10)  # Extend expiration
    
    # Format phone number
    formatted_phone = format_phone_number(pending["phone"])
    
    # Send WhatsApp OTP
    whatsapp_sent = send_whatsapp_otp(formatted_phone, phone_otp, pending["full_name"])
    
    if not whatsapp_sent:
        return templates.TemplateResponse("auth/verify.html", {
            "request": request,
            "email": email,
            "error": "Failed to send WhatsApp OTP. Please try again."
        })
    
    # Redirect to phone verification page
    return RedirectResponse(f"/auth/verify-phone?email={email}", status_code=302)


@router.get("/resend-code")
async def resend_code(
    email: str,
    db: Session = Depends(get_db)
):
    """Resend verification code."""
    registration_key = email.lower()
    
    if registration_key not in pending_registrations:
        return RedirectResponse("/auth/register", status_code=302)
    
    pending = pending_registrations[registration_key]
    
    # Generate new code
    new_code = generate_verification_code()
    pending["verification_code"] = new_code
    pending["expires_at"] = datetime.utcnow() + timedelta(minutes=10)
    
    # Resend email
    send_verification_email(email, new_code, pending["full_name"])
    
    return RedirectResponse(f"/auth/verify?email={email}", status_code=302)


@router.get("/verify-phone", response_class=HTMLResponse)
async def verify_phone_page(
    request: Request,
    email: str,
    db: Session = Depends(get_db)
):
    """Show phone verification page."""
    user = await get_current_user_optional(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    
    registration_key = email.lower()
    if registration_key not in pending_registrations:
        return RedirectResponse("/auth/register", status_code=302)
    
    pending = pending_registrations[registration_key]
    
    return templates.TemplateResponse("auth/verify_phone.html", {
        "request": request,
        "email": email,
        "phone": pending.get("phone", "")
    })


@router.post("/verify-phone")
async def verify_phone(
    request: Request,
    email: str = Form(...),
    otp: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verify phone OTP and create user account."""
    registration_key = email.lower()
    
    # Check if pending registration exists
    if registration_key not in pending_registrations:
        return templates.TemplateResponse("auth/verify_phone.html", {
            "request": request,
            "email": email,
            "phone": "",
            "error": "Registration expired or not found. Please register again."
        })
    
    pending = pending_registrations[registration_key]
    
    # Check if expired
    if datetime.utcnow() > pending["expires_at"]:
        del pending_registrations[registration_key]
        return templates.TemplateResponse("auth/verify_phone.html", {
            "request": request,
            "email": email,
            "phone": pending.get("phone", ""),
            "error": "OTP code expired. Please register again."
        })
    
    # Check if email was verified first
    if not pending.get("email_verified", False):
        return templates.TemplateResponse("auth/verify_phone.html", {
            "request": request,
            "email": email,
            "phone": pending.get("phone", ""),
            "error": "Please verify your email first."
        })
    
    # Verify OTP
    if otp != pending.get("phone_otp_code", ""):
        return templates.TemplateResponse("auth/verify_phone.html", {
            "request": request,
            "email": email,
            "phone": pending.get("phone", ""),
            "error": "Invalid OTP code. Please try again."
        })
    
    # Both verifications passed - create the user
    from app.services.encryption_service import generate_rsa_keypair
    
    # Generate encryption keys for the user
    public_key, private_key = generate_rsa_keypair()
    
    user = User(
        full_name=pending["full_name"],
        email=pending["email"],
        hashed_password=pending["password_hash"],
        phone=format_phone_number(pending["phone"]),
        role=UserRole(pending["role"]),
        wallet_balance=0.0,
        profile_picture=None,
        email_verified=True,
        public_key=public_key,
        private_key_encrypted=private_key  # Store directly (database is encrypted at rest)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Save profile picture if provided
    if pending.get("profile_picture_data") and pending.get("profile_picture_filename"):
        try:
            from pathlib import Path
            # Get file extension
            filename = pending["profile_picture_filename"]
            ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
            
            # Save file
            upload_dir = Path("app/static/uploads/profiles")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            new_filename = f"user_{user.id}.{ext}"
            filepath = upload_dir / new_filename
            
            # Write the file data
            with open(filepath, "wb") as f:
                f.write(pending["profile_picture_data"])
            
            # Update user with picture path
            user.profile_picture = f"/static/uploads/profiles/{new_filename}"
            db.commit()
        except Exception as e:
            print(f"Error saving profile picture: {e}")
            # Don't fail registration if picture save fails
    
    # Clean up pending registration
    del pending_registrations[registration_key]
    
    # Auto-login after verification
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        "access_token", 
        token, 
        httponly=True, 
        secure=False,  # Set to True in production with HTTPS
        samesite="Lax",  # CSRF protection
        max_age=3600
    )
    return response


@router.get("/resend-phone-otp")
async def resend_phone_otp(
    email: str,
    db: Session = Depends(get_db)
):
    """Resend phone OTP code."""
    registration_key = email.lower()
    
    if registration_key not in pending_registrations:
        return RedirectResponse("/auth/register", status_code=302)
    
    pending = pending_registrations[registration_key]
    
    # Generate new OTP
    new_otp = generate_otp_code()
    pending["phone_otp_code"] = new_otp
    pending["expires_at"] = datetime.utcnow() + timedelta(minutes=10)
    
    # Resend WhatsApp
    formatted_phone = format_phone_number(pending["phone"])
    send_whatsapp_otp(formatted_phone, new_otp, pending["full_name"])
    
    return RedirectResponse(f"/auth/verify-phone?email={email}", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    success: str = "",
    db: Session = Depends(get_db)
):
    user = await get_current_user_optional(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "success": success
    })


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "error": "Invalid email or password."
        })

    if not user.is_active:
        return templates.TemplateResponse("auth/login.html", {
            "request": request, "error": "Account is inactive."
        })

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        "access_token", 
        token, 
        httponly=True, 
        secure=False,  # Set to True in production with HTTPS
        samesite="Lax",  # CSRF protection
        max_age=3600
    )
    return response


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    email: str = "",
    db: Session = Depends(get_db)
):
    """Show forgot password page."""
    return templates.TemplateResponse("auth/forgot_password.html", {
        "request": request,
        "email": email
    })


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Send password reset code to user's email."""
    # Find user by email
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Don't reveal if email exists - security best practice
        return templates.TemplateResponse("auth/forgot_password.html", {
            "request": request,
            "success": "If that email exists, we've sent a reset code. Please check your inbox."
        })
    
    # Generate reset code
    reset_code = generate_verification_code()
    
    # Store reset token
    reset_key = email.lower()
    password_reset_tokens[reset_key] = {
        "code": reset_code,
        "user_id": user.id,
        "expires_at": datetime.utcnow() + timedelta(minutes=10)
    }
    
    # Send reset email
    email_sent = send_password_reset_email(email, reset_code, user.full_name)
    
    if not email_sent:
        return templates.TemplateResponse("auth/forgot_password.html", {
            "request": request,
            "error": "Failed to send reset email. Please try again."
        })
    
    # Redirect to reset page
    return RedirectResponse(f"/auth/reset-password?email={email}", status_code=302)


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    email: str,
    db: Session = Depends(get_db)
):
    """Show reset password page."""
    return templates.TemplateResponse("auth/reset_password.html", {
        "request": request,
        "email": email
    })


@router.post("/reset-password")
async def reset_password(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Reset user password with code."""
    reset_key = email.lower()
    
    # Check if reset token exists
    if reset_key not in password_reset_tokens:
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request,
            "email": email,
            "error": "Invalid or expired reset code. Please request a new one."
        })
    
    token_data = password_reset_tokens[reset_key]
    
    # Check if expired
    if datetime.utcnow() > token_data["expires_at"]:
        del password_reset_tokens[reset_key]
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request,
            "email": email,
            "error": "Reset code expired. Please request a new one."
        })
    
    # Verify code
    if code != token_data["code"]:
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request,
            "email": email,
            "error": "Invalid reset code. Please try again."
        })
    
    # Validate passwords match
    if new_password != confirm_password:
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request,
            "email": email,
            "error": "Passwords do not match. Please try again."
        })
    
    # Validate password length
    if len(new_password) < 6:
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request,
            "email": email,
            "error": "Password must be at least 6 characters."
        })
    
    # Update password
    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    if not user:
        return templates.TemplateResponse("auth/reset_password.html", {
            "request": request,
            "email": email,
            "error": "User not found."
        })
    
    user.hashed_password = hash_password(new_password)
    db.commit()
    
    # Clean up token
    del password_reset_tokens[reset_key]
    
    # Redirect to login with success message
    return RedirectResponse("/auth/login?success=Password reset successfully! Please log in.", status_code=302)


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response


# --- JSON API endpoints for external clients ---------------------------------

@router.post("/api/register", response_model=Token)
async def api_register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        phone=user_data.phone,
        role=user_data.role,
        wallet_balance=0.0
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role.value,
        user_id=user.id,
        full_name=user.full_name
    )


@router.post("/api/login", response_model=Token)
async def api_login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role.value,
        user_id=user.id,
        full_name=user.full_name
    )
