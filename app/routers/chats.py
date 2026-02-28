from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Dict, List
import json

from app.database import get_db
from app.models.models import User, Chat, Message, BookingProposal, Review, Booking, WorkerProfile
from app.schemas.chat_schemas import (
    ChatCreate, MessageCreate, BookingProposalCreate, BookingProposalAccept, ReviewCreate
)
from app.services.auth_service import get_current_user
from app.services.chat_service import (
    get_or_create_chat, get_user_chats, send_message, mark_messages_read,
    create_booking_proposal, accept_booking_proposal, reject_booking_proposal
)

router = APIRouter(prefix="/chats", tags=["Chats"])
templates = Jinja2Templates(directory="app/templates")


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except:
                self.disconnect(user_id)


manager = ConnectionManager()


# --- HTML Routes --------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def chats_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all chats for current user."""
    chats = get_user_chats(db, current_user.id)
    return templates.TemplateResponse("chats/list.html", {
        "request": request,
        "current_user": current_user,
        "chats": chats
    })


@router.get("/{chat_id}", response_class=HTMLResponse)
async def chat_detail(
    chat_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Chat conversation view."""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Verify user is part of chat
    if current_user.id not in [chat.initiator_id, chat.receiver_id]:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get messages
    messages = db.query(Message).filter(
        Message.chat_id == chat_id
    ).order_by(Message.created_at).all()
    
    # Decrypt messages for current user
    from app.services.chat_service import decrypt_message_for_user
    decrypted_messages = []
    for msg in messages:
        decrypted_content = decrypt_message_for_user(msg, current_user)
        # Create a dict with decrypted content
        msg_dict = {
            "id": msg.id,
            "sender_id": msg.sender_id,
            "content": decrypted_content,
            "created_at": msg.created_at,
            "is_read": msg.is_read
        }
        decrypted_messages.append(msg_dict)

    # Mark messages as read
    mark_messages_read(db, chat_id, current_user.id)

    # Get other participant
    other_user_id = chat.receiver_id if chat.initiator_id == current_user.id else chat.initiator_id
    other_user = db.query(User).filter(User.id == other_user_id).first()

    # Get booking proposals for this chat
    proposals = db.query(BookingProposal).filter(
        BookingProposal.chat_id == chat_id
    ).order_by(BookingProposal.created_at.desc()).all()

    # Check if there's a completed booking that needs review
    completed_booking = None
    existing_review = None
    can_review = False
    
    for proposal in proposals:
        if proposal.booking_id:
            booking = db.query(Booking).filter(Booking.id == proposal.booking_id).first()
            if booking and booking.status.value == 'completed':
                completed_booking = booking
                # Check if review already exists
                existing_review = db.query(Review).filter(Review.booking_id == booking.id).first()
                # Client can review if booking is complete and no review exists yet
                can_review = (current_user.id == booking.client_id and not existing_review)
                break

    return templates.TemplateResponse("chats/detail.html", {
        "request": request,
        "current_user": current_user,
        "chat": chat,
        "messages": decrypted_messages,
        "other_user": other_user,
        "proposals": proposals,
        "completed_booking": completed_booking,
        "can_review": can_review,
        "existing_review": existing_review,
    })


@router.post("/start")
async def start_chat(
    receiver_id: int = Form(...),
    job_id: int = Form(None),
    initial_message: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new chat (or open existing one)."""
    if receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot chat with yourself")

    chat = get_or_create_chat(db, current_user.id, receiver_id, job_id)

    # Send initial message if provided
    if initial_message:
        send_message(db, chat.id, current_user.id, initial_message)

    return RedirectResponse(f"/chats/{chat.id}", status_code=302)


# --- WebSocket Endpoint -------------------------------------------------------

@router.websocket("/ws/{chat_id}/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time messaging."""
    await manager.connect(user_id, websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "message":
                # Save message to database
                message = send_message(
                    db, chat_id, user_id, message_data.get("content", "")
                )

                # Get sender info
                sender = db.query(User).filter(User.id == user_id).first()

                # Broadcast to both parties
                chat = db.query(Chat).filter(Chat.id == chat_id).first()
                recipient_id = chat.receiver_id if chat.initiator_id == user_id else chat.initiator_id
                recipient = db.query(User).filter(User.id == recipient_id).first()
                
                # Decrypt message for each user
                from app.services.chat_service import decrypt_message_for_user
                
                # Decrypt for sender (current user)
                sender_content = decrypt_message_for_user(message, sender)
                
                # Decrypt for recipient
                recipient_content = decrypt_message_for_user(message, recipient)
                
                # Send to sender (confirmation) with decrypted content
                sender_msg = {
                    "type": "message",
                    "id": message.id,
                    "sender_id": user_id,
                    "sender_name": sender.full_name if sender else "Unknown",
                    "content": sender_content,
                    "created_at": message.created_at.isoformat()
                }
                await manager.send_personal_message(user_id, sender_msg)
                
                # Send to recipient with decrypted content
                recipient_msg = {
                    "type": "message",
                    "id": message.id,
                    "sender_id": user_id,
                    "sender_name": sender.full_name if sender else "Unknown",
                    "content": recipient_content,
                    "created_at": message.created_at.isoformat()
                }
                await manager.send_personal_message(recipient_id, recipient_msg)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(user_id)


# --- Booking Proposal Routes --------------------------------------------------

@router.post("/{chat_id}/proposals")
async def create_proposal(
    chat_id: int,
    worker_id: int = Form(...),
    client_id: int = Form(...),
    agreed_rate: float = Form(...),
    duration_hours: float = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a booking proposal in the chat."""
    
    # Always create a generic job for the proposal
    from app.models.models import Job, SkillCategory
    
    # Get worker's skill for the job
    worker_profile = db.query(WorkerProfile).filter(WorkerProfile.user_id == worker_id).first()
    skill = worker_profile.skill_category if worker_profile else SkillCategory.other
    
    # Create a job for this negotiation
    job = Job(
        client_id=client_id,
        title=f"Service - {agreed_rate} QAR/hr",
        description=f"Negotiated through chat. Rate: QAR {agreed_rate}/hr for {duration_hours} hours.",
        skill_required=skill,
        duration_hours=duration_hours,
        budget=agreed_rate * duration_hours,
        location="Negotiated in chat",
        is_open=False  # Already being filled
    )
    db.add(job)
    db.flush()  # Get the ID without committing
    job_id = job.id
    
    total_amount = agreed_rate * duration_hours
    
    # If current user is the client, check if they have enough funds
    if current_user.id == client_id:
        # Calculate total cost including 10% platform fee
        required_funds = total_amount * 1.10
        
        if current_user.wallet_balance < required_funds:
            return RedirectResponse(
                f"/bookings/wallet/topup?error=Insufficient funds to create this proposal. You need at least QAR {required_funds:.2f} (total + 10% fee). Your current balance: QAR {current_user.wallet_balance:.2f}&chat_id={chat_id}",
                status_code=302
            )
    
    proposal = create_booking_proposal(
        db, chat_id, current_user.id, job_id, worker_id, client_id,
        agreed_rate, duration_hours, notes if notes else None
    )
    
    # Broadcast proposal creation via WebSocket
    from app.routers.chats import manager
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat:
        recipient_id = chat.receiver_id if chat.initiator_id == current_user.id else chat.initiator_id
        
        broadcast_msg = {
            "type": "proposal_created",
            "proposal_id": proposal.id,
            "message": "New booking proposal created! Please refresh to see it."
        }
        
        # Send to both parties
        await manager.send_personal_message(current_user.id, broadcast_msg)
        await manager.send_personal_message(recipient_id, broadcast_msg)
    
    return RedirectResponse(f"/chats/{chat_id}#proposal-{proposal.id}", status_code=302)


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Accept a booking proposal."""
    try:
        # Get the proposal first to check wallet if user is client
        proposal = db.query(BookingProposal).filter(BookingProposal.id == proposal_id).first()
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # If current user is the client and accepting, check wallet BEFORE processing
        if current_user.id == proposal.client_id and not proposal.client_accepted:
            required_funds = proposal.total_amount * 1.10  # total + 10% fee
            
            if current_user.wallet_balance < required_funds:
                return RedirectResponse(
                    f"/bookings/wallet/topup?error=Insufficient wallet balance. Required: QAR {required_funds:.2f} (total + 10% fee). Your current balance: QAR {current_user.wallet_balance:.2f}&chat_id={proposal.chat_id}&proposal_id={proposal_id}",
                    status_code=302
                )
        
        # Now proceed with acceptance
        proposal = accept_booking_proposal(db, proposal_id, current_user.id)
        return RedirectResponse(f"/chats/{proposal.chat_id}#proposal-{proposal_id}", status_code=302)
    except HTTPException as e:
        # Get the proposal to know which chat it belongs to
        proposal = db.query(BookingProposal).filter(BookingProposal.id == proposal_id).first()
        
        # If insufficient funds (fallback - shouldn't reach here with above check)
        if "Insufficient wallet balance" in e.detail:
            return RedirectResponse(
                f"/bookings/wallet/topup?error={e.detail}&chat_id={proposal.chat_id if proposal else ''}&proposal_id={proposal_id}",
                status_code=302
            )
        # Other errors - redirect to chat with error
        if proposal:
            return RedirectResponse(
                f"/chats/{proposal.chat_id}?error={e.detail}",
                status_code=302
            )
        raise e


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reject a booking proposal."""
    proposal = reject_booking_proposal(db, proposal_id, current_user.id)
    return RedirectResponse(f"/chats/{proposal.chat_id}#proposal-{proposal_id}", status_code=302)


# --- Review Routes ------------------------------------------------------------

@router.post("/{chat_id}/review")
async def submit_review(
    chat_id: int,
    booking_id: int = Form(...),
    rating: int = Form(...),
    review_comment: str = Form(""),
    review_anonymous: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit a review for a completed booking."""
    # Verify booking exists and is completed
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status.value != 'completed':
        raise HTTPException(status_code=400, detail="Can only review completed bookings")
    
    # Verify current user is the client
    if current_user.id != booking.client_id:
        raise HTTPException(status_code=403, detail="Only the client can review")
    
    # Check if review already exists
    existing = db.query(Review).filter(Review.booking_id == booking_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Review already submitted for this booking")
    
    # Validate rating
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    
    # Convert checkbox to boolean
    is_anonymous = (review_anonymous == "true")
    
    # Create review
    review = Review(
        booking_id=booking_id,
        worker_profile_id=booking.worker_profile_id,
        worker_id=booking.worker_id,
        reviewer_id=current_user.id,
        rating=rating,
        comment=review_comment if review_comment else None,
        is_anonymous=is_anonymous
    )
    db.add(review)
    db.commit()
    
    return RedirectResponse(f"/chats/{chat_id}#review-submitted", status_code=302)
