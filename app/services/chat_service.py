from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from fastapi import HTTPException
from datetime import datetime
from typing import List, Optional

from app.models.models import (
    Chat, Message, BookingProposal, User, Job, Booking,
    BookingProposalStatus, BookingStatus, PaymentStatus
)
from app.services.escrow_service import calculate_booking_fees, create_booking
from app.config import settings


def get_or_create_chat(
    db: Session,
    user1_id: int,
    user2_id: int,
    job_id: Optional[int] = None
) -> Chat:
    """Get existing chat or create new one between two users."""
    # Check if chat already exists (either direction)
    existing_chat = db.query(Chat).filter(
        or_(
            and_(Chat.initiator_id == user1_id, Chat.receiver_id == user2_id),
            and_(Chat.initiator_id == user2_id, Chat.receiver_id == user1_id)
        )
    ).first()

    if existing_chat:
        return existing_chat

    # Create new chat
    chat = Chat(
        initiator_id=user1_id,
        receiver_id=user2_id,
        job_id=job_id
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def get_user_chats(db: Session, user_id: int) -> List[dict]:
    """Get all chats for a user with last message and unread count."""
    chats = db.query(Chat).filter(
        or_(Chat.initiator_id == user_id, Chat.receiver_id == user_id)
    ).all()
    
    # Get current user for decryption
    current_user = db.query(User).filter(User.id == user_id).first()

    chat_list = []
    for chat in chats:
        # Determine other participant
        other_user_id = chat.receiver_id if chat.initiator_id == user_id else chat.initiator_id
        other_user = db.query(User).filter(User.id == other_user_id).first()

        # Get last message
        last_msg = db.query(Message).filter(
            Message.chat_id == chat.id
        ).order_by(desc(Message.created_at)).first()
        
        # Decrypt last message if it exists
        last_message_text = None
        if last_msg:
            last_message_text = decrypt_message_for_user(last_msg, current_user)
            # Truncate for preview
            if len(last_message_text) > 50:
                last_message_text = last_message_text[:50] + "..."

        # Count unread messages
        unread_count = db.query(Message).filter(
            Message.chat_id == chat.id,
            Message.sender_id != user_id,
            Message.is_read == False
        ).count()

        chat_list.append({
            "id": chat.id,
            "initiator_id": chat.initiator_id,
            "receiver_id": chat.receiver_id,
            "job_id": chat.job_id,
            "initiator_name": chat.initiator.full_name,
            "receiver_name": chat.receiver.full_name,
            "other_user_name": other_user.full_name if other_user else "Unknown",
            "other_user_id": other_user_id,
            "last_message": last_message_text,
            "last_message_time": last_msg.created_at if last_msg else chat.created_at,
            "unread_count": unread_count,
            "created_at": chat.created_at
        })

    # Sort by last activity
    chat_list.sort(key=lambda x: x["last_message_time"], reverse=True)
    return chat_list


def send_message(db: Session, chat_id: int, sender_id: int, content: str) -> Message:
    """Send an encrypted message in a chat."""
    from app.services.encryption_service import encrypt_message
    
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Verify sender is part of chat
    if sender_id not in [chat.initiator_id, chat.receiver_id]:
        raise HTTPException(status_code=403, detail="Not authorized to send message in this chat")

    # Get both users
    recipient_id = chat.receiver_id if sender_id == chat.initiator_id else chat.initiator_id
    recipient = db.query(User).filter(User.id == recipient_id).first()
    sender = db.query(User).filter(User.id == sender_id).first()
    
    if not recipient or not recipient.public_key:
        raise HTTPException(status_code=500, detail="Recipient encryption key not found")
    
    if not sender or not sender.public_key:
        raise HTTPException(status_code=500, detail="Sender encryption key not found")
    
    # Encrypt message TWICE - once for recipient, once for sender
    encrypted_content_recipient = encrypt_message(content, recipient.public_key)
    encrypted_content_sender = encrypt_message(content, sender.public_key)
    
    message = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        content=encrypted_content_recipient,  # For recipient
        content_sender=encrypted_content_sender,  # For sender
        is_encrypted=True,
        is_read=False
    )
    db.add(message)
    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    return message


def mark_messages_read(db: Session, chat_id: int, user_id: int):
    """Mark all messages in a chat as read for a user."""
    db.query(Message).filter(
        Message.chat_id == chat_id,
        Message.sender_id != user_id,
        Message.is_read == False
    ).update({"is_read": True})
    db.commit()


def create_booking_proposal(
    db: Session,
    chat_id: int,
    proposed_by_id: int,
    job_id: int,
    worker_id: int,
    client_id: int,
    agreed_rate: float,
    duration_hours: float,
    notes: Optional[str] = None
) -> BookingProposal:
    """Create a booking proposal in a chat."""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Verify proposer is part of chat
    if proposed_by_id not in [chat.initiator_id, chat.receiver_id]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Verify job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    total_amount = round(agreed_rate * duration_hours, 2)

    # Auto-accept if proposer is client
    client_accepted = (proposed_by_id == client_id)
    # Auto-accept if proposer is worker
    worker_accepted = (proposed_by_id == worker_id)

    proposal = BookingProposal(
        chat_id=chat_id,
        job_id=job_id,
        proposed_by_id=proposed_by_id,
        worker_id=worker_id,
        client_id=client_id,
        agreed_rate=agreed_rate,
        duration_hours=duration_hours,
        total_amount=total_amount,
        notes=notes,
        status=BookingProposalStatus.pending,
        client_accepted=client_accepted,
        worker_accepted=worker_accepted
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    # If both already accepted (shouldn't happen, but safety check)
    if proposal.client_accepted and proposal.worker_accepted:
        _finalize_booking_proposal(db, proposal)

    return proposal


def accept_booking_proposal(
    db: Session,
    proposal_id: int,
    user_id: int
) -> BookingProposal:
    """Accept a booking proposal. Creates booking when both parties accept."""
    proposal = db.query(BookingProposal).filter(BookingProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if proposal.status != BookingProposalStatus.pending:
        raise HTTPException(status_code=400, detail="Proposal is no longer pending")

    # Determine which party is accepting
    if user_id == proposal.client_id:
        proposal.client_accepted = True
    elif user_id == proposal.worker_id:
        proposal.worker_accepted = True
    else:
        raise HTTPException(status_code=403, detail="Not authorized to accept this proposal")

    # If both have accepted, create the booking
    if proposal.client_accepted and proposal.worker_accepted:
        _finalize_booking_proposal(db, proposal)

    db.commit()
    db.refresh(proposal)
    return proposal


def reject_booking_proposal(
    db: Session,
    proposal_id: int,
    user_id: int
) -> BookingProposal:
    """Reject a booking proposal."""
    proposal = db.query(BookingProposal).filter(BookingProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Verify user is part of the proposal
    if user_id not in [proposal.client_id, proposal.worker_id]:
        raise HTTPException(status_code=403, detail="Not authorized")

    proposal.status = BookingProposalStatus.rejected
    db.commit()
    db.refresh(proposal)
    return proposal


def _finalize_booking_proposal(db: Session, proposal: BookingProposal):
    """Internal: Create actual booking when both parties accept."""
    # Create the booking using existing escrow service
    from app.models.models import WorkerProfile

    worker_profile = db.query(WorkerProfile).filter(
        WorkerProfile.user_id == proposal.worker_id
    ).first()

    if not worker_profile:
        raise HTTPException(status_code=404, detail="Worker profile not found")

    # Calculate fees
    fees = calculate_booking_fees(proposal.total_amount, settings.PLATFORM_FEE_PERCENT)

    # Check client wallet
    client = db.query(User).filter(User.id == proposal.client_id).first()
    if client.wallet_balance < fees["client_total"]:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient wallet balance. Required: QAR {fees['client_total']:.2f}"
        )

    # Deduct from client wallet
    client.wallet_balance = round(client.wallet_balance - fees["client_total"], 2)

    # Create booking
    booking = Booking(
        job_id=proposal.job_id,
        client_id=proposal.client_id,
        worker_id=proposal.worker_id,
        worker_profile_id=worker_profile.id,
        agreed_rate=proposal.agreed_rate,
        duration_hours=proposal.duration_hours,
        total_amount=proposal.total_amount,
        platform_fee_percent=settings.PLATFORM_FEE_PERCENT,
        client_fee=fees["client_fee"],
        worker_fee=fees["worker_fee"],
        worker_payout=fees["worker_payout"],
        client_total=fees["client_total"],
        status=BookingStatus.confirmed,  # Start as confirmed since both agreed
        payment_status=PaymentStatus.held,
        notes=proposal.notes,
        client_confirmed_complete=False,
        worker_confirmed_complete=False,
        confirmed_at=datetime.utcnow()  # Set confirmation timestamp
    )
    db.add(booking)

    # Mark job as no longer open
    job = db.query(Job).filter(Job.id == proposal.job_id).first()
    if job:
        job.is_open = False

    # Update proposal
    proposal.status = BookingProposalStatus.accepted
    proposal.accepted_at = datetime.utcnow()
    db.flush()
    
    proposal.booking_id = booking.id

    # Record transaction
    from app.models.models import Transaction
    tx = Transaction(
        booking_id=booking.id,
        user_id=proposal.client_id,
        amount=-fees["client_total"],
        transaction_type="escrow_hold",
        description=f"Payment held in escrow for Job #{proposal.job_id}"
    )
    db.add(tx)


def decrypt_message_for_user(message: Message, user: User) -> str:
    """
    Decrypt a message for a specific user.
    Returns decrypted message or original if not encrypted.
    """
    from app.services.encryption_service import decrypt_message
    
    if not message.is_encrypted:
        return message.content
    
    if not user.private_key_encrypted:
        return "[Encryption keys not available]"
    
    # Use the correct encrypted content based on who is viewing
    # If user is the sender, use content_sender
    # If user is the recipient, use content
    if message.sender_id == user.id:
        encrypted_content = message.content_sender
    else:
        encrypted_content = message.content
    
    if not encrypted_content:
        return "[Message not encrypted for this user]"
    
    # Decrypt the message with user's private key
    return decrypt_message(encrypted_content, user.private_key_encrypted)
