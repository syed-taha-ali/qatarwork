from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.models import User, Job, WorkerProfile, UserRole, SkillCategory
from app.services.auth_service import get_current_user, get_current_user_optional

router = APIRouter(prefix="/jobs", tags=["Jobs"])
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


@router.get("/", response_class=HTMLResponse)
async def jobs_list(
    request: Request,
    skill: Optional[str] = None,
    verified_only: Optional[str] = None,
    db: Session = Depends(get_db)
):
    current_user = await get_current_user_optional(request, db)
    query = db.query(Job).filter(Job.is_open == True)
    
    if skill and skill in [s.value for s in SkillCategory]:
        query = query.filter(Job.skill_required == SkillCategory(skill))
    
    # Apply verified clients filter
    if verified_only == "true":
        query = query.join(User, Job.client_id == User.id).filter(User.verification_status == "approved")
    
    jobs = query.order_by(Job.created_at.desc()).all()
    return templates.TemplateResponse("jobs/list.html", {
        "request": request,
        "jobs": jobs,
        "current_user": current_user,
        "skill_labels": SKILL_LABELS,
        "skills": [s.value for s in SkillCategory],
        "selected_skill": skill or "",
        "verified_only": verified_only == "true",
    })


@router.get("/create", response_class=HTMLResponse)
async def create_job_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.client:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("jobs/form.html", {
        "request": request,
        "current_user": current_user,
        "skill_labels": SKILL_LABELS,
        "skills": [s.value for s in SkillCategory],
        "action": "create",
    })


@router.post("/create")
async def create_job(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    skill_required: str = Form(...),
    duration_hours: float = Form(...),
    budget: float = Form(...),
    location: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.client:
        raise HTTPException(status_code=403, detail="Only clients can post jobs")

    errors = []
    if duration_hours <= 0:
        errors.append("Duration must be positive.")
    if budget <= 0:
        errors.append("Budget must be positive.")
    
    # Check if client has enough funds (budget + 10% platform fee)
    required_funds = budget * 1.10  # budget + 10% fee
    if current_user.wallet_balance < required_funds:
        return RedirectResponse(
            f"/bookings/wallet/topup?error=Insufficient funds to post this job. You need at least QAR {required_funds:.2f} (budget + 10% fee). Your current balance: QAR {current_user.wallet_balance:.2f}&return_to=/jobs/create",
            status_code=302
        )

    if errors:
        return templates.TemplateResponse("jobs/form.html", {
            "request": request,
            "current_user": current_user,
            "skill_labels": SKILL_LABELS,
            "skills": [s.value for s in SkillCategory],
            "action": "create",
            "error": " ".join(errors),
        })

    job = Job(
        client_id=current_user.id,
        title=title,
        description=description,
        skill_required=SkillCategory(skill_required),
        duration_hours=duration_hours,
        budget=budget,
        location=location,
        is_open=True,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return RedirectResponse(f"/jobs/{job.id}", status_code=302)


@router.get("/{job_id}", response_class=HTMLResponse)
async def job_detail(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    current_user = await get_current_user_optional(request, db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return templates.TemplateResponse("jobs/detail.html", {
        "request": request,
        "job": job,
        "current_user": current_user,
        "skill_labels": SKILL_LABELS,
    })


@router.post("/{job_id}/delete")
async def delete_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id, Job.client_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_open:
        raise HTTPException(status_code=400, detail="Cannot delete a job that has a booking")
    db.delete(job)
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)
