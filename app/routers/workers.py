from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.models.models import User, WorkerProfile, UserRole, SkillCategory, Review
from app.schemas.schemas import WorkerProfileCreate, WorkerProfileOut
from app.services.auth_service import get_current_user, get_current_user_optional

router = APIRouter(prefix="/workers", tags=["Workers"])
templates = Jinja2Templates(directory="app/templates")

SKILL_LABELS = {
    # Skilled Trades
    "general_handyman": "General Handyman",
    "locksmith": "Locksmith",
    "electrician": "Electrician",
    "plumber": "Plumber",
    "carpenter": "Carpenter",
    "hvac_tech": "HVAC Technician",
    "painter": "Painter",
    "gardener": "Gardener",
    "chef": "Chef",
    "exterminator": "Exterminator",
    # Care & Personal Support
    "maid": "Maid / House Cleaner",
    "nanny": "Nanny",
    "nurse": "Nurse",
    "babysitter": "Babysitter",
    "pet_sitter": "Pet Sitter",
    # Other
    "other": "Other",
}

SKILL_CATEGORIES = {
    "Skilled Trades": [
        "general_handyman", "locksmith", "electrician", "plumber", 
        "carpenter", "hvac_tech", "painter", "gardener", "chef", "exterminator"
    ],
    "Care & Personal Support": [
        "maid", "nanny", "nurse", "babysitter", "pet_sitter"
    ],
    "Other": ["other"]
}


@router.get("/", response_class=HTMLResponse)
async def workers_list(
    request: Request,
    skill: Optional[str] = None,
    min_rating: Optional[float] = None,
    min_jobs: Optional[int] = None,
    verified_only: Optional[str] = None,
    db: Session = Depends(get_db)
):
    current_user = await get_current_user_optional(request, db)
    
    # Get all available workers
    workers_query = db.query(WorkerProfile).filter(WorkerProfile.is_available == True)
    
    # Apply skill filter
    if skill and skill in [s.value for s in SkillCategory]:
        workers_query = workers_query.filter(WorkerProfile.skill_category == SkillCategory(skill))
    
    # Apply verified filter
    if verified_only == "true":
        workers_query = workers_query.join(User).filter(User.verification_status == "approved")
    
    workers = workers_query.all()
    
    # Calculate ratings for each worker and apply filters
    filtered_workers = []
    for worker in workers:
        # Get reviews for this worker
        reviews = db.query(Review).filter(Review.worker_profile_id == worker.id).all()
        avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0
        review_count = len(reviews)
        
        # Apply rating filter
        if min_rating is not None and avg_rating < min_rating:
            continue
        
        # Apply jobs completed filter
        if min_jobs is not None and worker.total_jobs_completed < min_jobs:
            continue
        
        # Add rating data to worker object for template
        worker.avg_rating = avg_rating
        worker.review_count = review_count
        filtered_workers.append(worker)
    
    return templates.TemplateResponse("workers/list.html", {
        "request": request,
        "workers": filtered_workers,
        "current_user": current_user,
        "skill_labels": SKILL_LABELS,
        "skills": [s.value for s in SkillCategory],
        "selected_skill": skill or "",
        "min_rating": min_rating or 0,
        "min_jobs": min_jobs or 0,
        "verified_only": verified_only == "true",
    })


@router.get("/profile/create", response_class=HTMLResponse)
async def create_profile_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.worker:
        return RedirectResponse("/dashboard", status_code=302)
    if current_user.worker_profile:
        return RedirectResponse("/workers/profile/edit", status_code=302)
    return templates.TemplateResponse("workers/profile_form.html", {
        "request": request,
        "current_user": current_user,
        "skill_labels": SKILL_LABELS,
        "skills": [s.value for s in SkillCategory],
        "action": "create",
    })


@router.post("/profile/create")
async def create_profile(
    request: Request,
    skill_category: str = Form(...),
    hourly_rate: float = Form(...),
    bio: str = Form(""),
    location: str = Form(""),
    years_experience: int = Form(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.worker:
        raise HTTPException(status_code=403, detail="Only workers can create profiles")

    if current_user.worker_profile:
        return RedirectResponse("/workers/profile/edit", status_code=302)

    if hourly_rate <= 0:
        return templates.TemplateResponse("workers/profile_form.html", {
            "request": request, "current_user": current_user,
            "skill_labels": SKILL_LABELS,
            "skills": [s.value for s in SkillCategory],
            "action": "create",
            "error": "Hourly rate must be positive."
        })

    profile = WorkerProfile(
        user_id=current_user.id,
        skill_category=SkillCategory(skill_category),
        hourly_rate=hourly_rate,
        bio=bio if bio else None,
        location=location if location else None,
        years_experience=years_experience,
        is_available=True,
    )
    db.add(profile)
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/profile/edit", response_class=HTMLResponse)
async def edit_profile_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.worker:
        return RedirectResponse("/dashboard", status_code=302)
    if not current_user.worker_profile:
        return RedirectResponse("/workers/profile/create", status_code=302)
    return templates.TemplateResponse("workers/profile_form.html", {
        "request": request,
        "current_user": current_user,
        "profile": current_user.worker_profile,
        "skill_labels": SKILL_LABELS,
        "skills": [s.value for s in SkillCategory],
        "action": "edit",
    })


@router.post("/profile/edit")
async def edit_profile(
    request: Request,
    skill_category: str = Form(...),
    hourly_rate: float = Form(...),
    bio: str = Form(""),
    location: str = Form(""),
    years_experience: int = Form(0),
    is_available: str = Form("on"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    profile = current_user.worker_profile
    if not profile:
        return RedirectResponse("/workers/profile/create", status_code=302)

    profile.skill_category = SkillCategory(skill_category)
    profile.hourly_rate = hourly_rate
    profile.bio = bio if bio else None
    profile.location = location if location else None
    profile.years_experience = years_experience
    profile.is_available = (is_available == "on")
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/{worker_id}", response_class=HTMLResponse)
async def worker_detail(
    worker_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    current_user = await get_current_user_optional(request, db)
    profile = db.query(WorkerProfile).filter(WorkerProfile.user_id == worker_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    # Get reviews
    reviews = db.query(Review).filter(
        Review.worker_profile_id == profile.id
    ).order_by(Review.created_at.desc()).all()
    
    # Calculate average rating
    avg_rating = None
    if reviews:
        avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1)
    
    return templates.TemplateResponse("workers/detail.html", {
        "request": request,
        "profile": profile,
        "current_user": current_user,
        "skill_labels": SKILL_LABELS,
        "reviews": reviews,
        "avg_rating": avg_rating,
    })
