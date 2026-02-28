from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User, Booking, UserRole, BookingStatus
from app.services.auth_service import get_current_user
from app.services.escrow_service import (
    create_booking, confirm_booking, complete_booking, cancel_booking, topup_wallet
)

router = APIRouter(prefix="/bookings", tags=["Bookings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def my_bookings(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == UserRole.client:
        bookings = db.query(Booking).filter(
            Booking.client_id == current_user.id
        ).order_by(Booking.created_at.desc()).all()
    else:
        bookings = db.query(Booking).filter(
            Booking.worker_id == current_user.id
        ).order_by(Booking.created_at.desc()).all()

    return templates.TemplateResponse("bookings/list.html", {
        "request": request,
        "bookings": bookings,
        "current_user": current_user,
    })


@router.post("/create")
async def create_booking_route(
    request: Request,
    job_id: int = Form(...),
    worker_id: int = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.client:
        raise HTTPException(status_code=403, detail="Only clients can create bookings")

    try:
        booking = create_booking(
            db=db,
            job_id=job_id,
            worker_id=worker_id,
            client_id=current_user.id,
            notes=notes if notes else None
        )
        return RedirectResponse(f"/bookings/{booking.id}", status_code=302)
    except HTTPException as e:
        # Redirect back to job with error
        return RedirectResponse(
            f"/jobs/{job_id}?error={e.detail}",
            status_code=302
        )


@router.get("/{booking_id}", response_class=HTMLResponse)
async def booking_detail(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Only client or worker of this booking can view it
    if current_user.id not in [booking.client_id, booking.worker_id]:
        raise HTTPException(status_code=403, detail="Access denied")

    # Find the chat for this booking (via proposal)
    from app.models.models import BookingProposal
    chat_id = None
    proposal = db.query(BookingProposal).filter(BookingProposal.booking_id == booking_id).first()
    if proposal:
        chat_id = proposal.chat_id

    return templates.TemplateResponse("bookings/detail.html", {
        "request": request,
        "booking": booking,
        "current_user": current_user,
        "chat_id": chat_id,
    })


@router.post("/{booking_id}/confirm")
async def confirm_booking_route(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        booking = confirm_booking(db, booking_id, current_user.id)
        return RedirectResponse(f"/bookings/{booking_id}", status_code=302)
    except HTTPException as e:
        raise e


@router.post("/{booking_id}/complete")
async def complete_booking_route(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        booking = complete_booking(db, booking_id, current_user.id)  # Changed to user_id
        return RedirectResponse(f"/bookings/{booking_id}", status_code=302)
    except HTTPException as e:
        raise e


@router.post("/{booking_id}/cancel")
async def cancel_booking_route(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        booking = cancel_booking(db, booking_id, current_user.id)
        return RedirectResponse(f"/bookings/{booking_id}", status_code=302)
    except HTTPException as e:
        raise e


# --- Wallet top-up -----------------------------------------------------------

@router.get("/wallet/topup", response_class=HTMLResponse)
async def topup_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return templates.TemplateResponse("bookings/wallet_topup.html", {
        "request": request,
        "current_user": current_user,
    })


@router.post("/wallet/topup")
async def topup_wallet_route(
    amount: float = Form(...),
    chat_id: int = Form(None),
    proposal_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    topup_wallet(db, current_user.id, amount)
    
    # Redirect back to chat if provided
    if chat_id:
        anchor = f"#proposal-{proposal_id}" if proposal_id else ""
        return RedirectResponse(f"/chats/{chat_id}{anchor}?success=Funds added! You can now accept the proposal.", status_code=302)
    
    return RedirectResponse("/dashboard?success=Wallet topped up successfully!", status_code=302)
