from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import (
    User, Job, Booking, WorkerProfile, Transaction, BookingProposal,
    UserRole, BookingStatus, BookingProposalStatus
)
from app.services.auth_service import get_current_user, get_current_user_optional

router = APIRouter(tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    current_user = await get_current_user_optional(request, db)

    # Stats for landing page
    total_workers = db.query(WorkerProfile).filter(WorkerProfile.is_available == True).count()
    total_jobs = db.query(Job).filter(Job.is_open == True).count()
    total_completed = db.query(Booking).filter(Booking.status == BookingStatus.completed).count()

    # Featured workers
    featured_workers = db.query(WorkerProfile).filter(
        WorkerProfile.is_available == True
    ).order_by(WorkerProfile.total_jobs_completed.desc()).limit(6).all()

    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user,
        "total_workers": total_workers,
        "total_jobs": total_jobs,
        "total_completed": total_completed,
        "featured_workers": featured_workers,
    })


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Redirect admin to admin panel
    if current_user.role == UserRole.admin:
        return RedirectResponse("/admin/verifications", status_code=302)
    
    if current_user.role == UserRole.client:
        my_jobs = db.query(Job).filter(
            Job.client_id == current_user.id
        ).order_by(Job.created_at.desc()).limit(5).all()

        my_bookings = db.query(Booking).filter(
            Booking.client_id == current_user.id
        ).order_by(Booking.created_at.desc()).limit(5).all()

        active_bookings = db.query(Booking).filter(
            Booking.client_id == current_user.id,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed, BookingStatus.in_progress])
        ).count()

        # Pending proposals - either sent by me or received
        pending_proposals = db.query(BookingProposal).filter(
            BookingProposal.status == BookingProposalStatus.pending,
            (BookingProposal.client_id == current_user.id)
        ).order_by(BookingProposal.created_at.desc()).all()

        txns = db.query(Transaction).filter(
            Transaction.user_id == current_user.id
        ).order_by(Transaction.created_at.desc()).limit(10).all()

        return templates.TemplateResponse("dashboard/client.html", {
            "request": request,
            "current_user": current_user,
            "my_jobs": my_jobs,
            "my_bookings": my_bookings,
            "active_bookings": active_bookings,
            "pending_proposals": pending_proposals,
            "transactions": txns,
        })

    else:  # worker
        profile = current_user.worker_profile
        my_bookings = db.query(Booking).filter(
            Booking.worker_id == current_user.id
        ).order_by(Booking.created_at.desc()).limit(5).all()

        active_bookings = db.query(Booking).filter(
            Booking.worker_id == current_user.id,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed, BookingStatus.in_progress])
        ).count()

        # Pending proposals - either sent by me or received
        pending_proposals = db.query(BookingProposal).filter(
            BookingProposal.status == BookingProposalStatus.pending,
            (BookingProposal.worker_id == current_user.id)
        ).order_by(BookingProposal.created_at.desc()).all()

        # Get reviews for this worker
        reviews = []
        avg_rating = None
        if profile:
            from app.models.models import Review
            reviews = db.query(Review).filter(
                Review.worker_profile_id == profile.id
            ).order_by(Review.created_at.desc()).all()
            
            if reviews:
                avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1)

        txns = db.query(Transaction).filter(
            Transaction.user_id == current_user.id
        ).order_by(Transaction.created_at.desc()).limit(10).all()

        total_earned = sum(t.amount for t in txns if t.amount > 0)

        return templates.TemplateResponse("dashboard/worker.html", {
            "request": request,
            "current_user": current_user,
            "profile": profile,
            "my_bookings": my_bookings,
            "active_bookings": active_bookings,
            "pending_proposals": pending_proposals,
            "reviews": reviews,
            "avg_rating": avg_rating,
            "transactions": txns,
            "total_earned": total_earned,
        })
