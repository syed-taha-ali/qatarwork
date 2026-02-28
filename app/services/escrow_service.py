from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime

from app.config import settings
from app.models.models import Booking, Transaction, User, WorkerProfile, Job, BookingStatus, PaymentStatus


def calculate_booking_fees(total_amount: float, fee_percent: float) -> dict:
    """
    Escrow fee structure:
    - Client pays: total_amount + client_fee (fee_percent of total)
    - Worker receives: total_amount - worker_fee (fee_percent of total)
    - Platform earns: client_fee + worker_fee
    """
    client_fee = round(total_amount * (fee_percent / 100), 2)
    worker_fee = round(total_amount * (fee_percent / 100), 2)
    worker_payout = round(total_amount - worker_fee, 2)
    client_total = round(total_amount + client_fee, 2)

    return {
        "client_fee": client_fee,
        "worker_fee": worker_fee,
        "worker_payout": worker_payout,
        "client_total": client_total,
    }


def create_booking(
    db: Session,
    job_id: int,
    worker_id: int,
    client_id: int,
    notes: str = None
) -> Booking:
    """Create a booking and hold payment in escrow."""
    # Fetch job
    job = db.query(Job).filter(Job.id == job_id, Job.is_open == True).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already booked")

    if job.client_id != client_id:
        raise HTTPException(status_code=403, detail="You can only book workers for your own jobs")

    # Fetch worker profile
    worker_profile = db.query(WorkerProfile).filter(
        WorkerProfile.user_id == worker_id,
        WorkerProfile.is_available == True
    ).first()
    if not worker_profile:
        raise HTTPException(status_code=404, detail="Worker not found or unavailable")

    # Check existing booking
    existing = db.query(Booking).filter(Booking.job_id == job_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="This job already has a booking")

    # Financial calculations
    total_amount = round(worker_profile.hourly_rate * job.duration_hours, 2)
    fees = calculate_booking_fees(total_amount, settings.PLATFORM_FEE_PERCENT)

    # Check client wallet
    client = db.query(User).filter(User.id == client_id).first()
    if client.wallet_balance < fees["client_total"]:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient wallet balance. Required: QAR {fees['client_total']:.2f}, "
                   f"Available: QAR {client.wallet_balance:.2f}"
        )

    # Deduct from client wallet (funds now in escrow = held by platform)
    client.wallet_balance = round(client.wallet_balance - fees["client_total"], 2)

    # Create booking
    booking = Booking(
        job_id=job_id,
        client_id=client_id,
        worker_id=worker_id,
        worker_profile_id=worker_profile.id,
        agreed_rate=worker_profile.hourly_rate,
        duration_hours=job.duration_hours,
        total_amount=total_amount,
        platform_fee_percent=settings.PLATFORM_FEE_PERCENT,
        client_fee=fees["client_fee"],
        worker_fee=fees["worker_fee"],
        worker_payout=fees["worker_payout"],
        client_total=fees["client_total"],
        status=BookingStatus.pending,
        payment_status=PaymentStatus.held,
        notes=notes,
    )
    db.add(booking)

    # Mark job as no longer open
    job.is_open = False

    db.flush()  # get booking.id before committing

    # Record transaction - client debit
    tx_client = Transaction(
        booking_id=booking.id,
        user_id=client_id,
        amount=-fees["client_total"],
        transaction_type="escrow_hold",
        description=f"Payment held in escrow for Job #{job_id}: {job.title}"
    )
    db.add(tx_client)
    db.commit()
    db.refresh(booking)
    return booking


def confirm_booking(db: Session, booking_id: int, client_id: int) -> Booking:
    """Client confirms the booking (worker accepted)."""
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.client_id == client_id
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != BookingStatus.pending:
        raise HTTPException(status_code=400, detail="Booking is not in pending state")

    booking.status = BookingStatus.confirmed
    booking.confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(booking)
    return booking


def complete_booking(db: Session, booking_id: int, user_id: int) -> Booking:
    """
    Mark job as complete from user's perspective.
    Payment only releases when BOTH client AND worker confirm.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Verify user is part of booking
    if user_id not in [booking.client_id, booking.worker_id]:
        raise HTTPException(status_code=403, detail="Not authorized")

    allowed_statuses = [BookingStatus.confirmed, BookingStatus.in_progress]
    if booking.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Booking must be confirmed or in-progress")

    # Mark confirmation based on who is calling
    if user_id == booking.client_id:
        booking.client_confirmed_complete = True
    elif user_id == booking.worker_id:
        booking.worker_confirmed_complete = True

    # Only release payment when BOTH have confirmed
    if booking.client_confirmed_complete and booking.worker_confirmed_complete:
        # Release payment to worker
        worker = db.query(User).filter(User.id == booking.worker_id).first()
        worker.wallet_balance = round(worker.wallet_balance + booking.worker_payout, 2)

        # Update booking status
        booking.status = BookingStatus.completed
        booking.payment_status = PaymentStatus.released
        booking.completed_at = datetime.utcnow()

        # Update worker stats
        worker_profile = db.query(WorkerProfile).filter(
            WorkerProfile.id == booking.worker_profile_id
        ).first()
        worker_profile.total_jobs_completed += 1
        worker_profile.is_available = True

        # Record transaction - worker credit
        tx_worker = Transaction(
            booking_id=booking_id,
            user_id=booking.worker_id,
            amount=booking.worker_payout,
            transaction_type="escrow_release",
            description=f"Payment released for Job #{booking.job_id} (fee deducted: QAR {booking.worker_fee:.2f})"
        )
        db.add(tx_worker)

    db.commit()
    db.refresh(booking)
    return booking


def cancel_booking(db: Session, booking_id: int, user_id: int) -> Booking:
    """Cancel a booking and refund client if payment was held."""
    booking = db.query(Booking).filter(
        Booking.id == booking_id
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.client_id != user_id and booking.worker_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")

    if booking.status in [BookingStatus.completed, BookingStatus.cancelled]:
        raise HTTPException(status_code=400, detail="Booking cannot be cancelled in its current state")

    # Refund client if payment was held
    if booking.payment_status == PaymentStatus.held:
        client = db.query(User).filter(User.id == booking.client_id).first()
        client.wallet_balance = round(client.wallet_balance + booking.client_total, 2)

        # Record refund transaction
        tx_refund = Transaction(
            booking_id=booking_id,
            user_id=booking.client_id,
            amount=booking.client_total,
            transaction_type="refund",
            description=f"Refund for cancelled booking #{booking_id}"
        )
        db.add(tx_refund)
        booking.payment_status = PaymentStatus.refunded

    # Re-open job
    job = db.query(Job).filter(Job.id == booking.job_id).first()
    if job:
        job.is_open = True

    booking.status = BookingStatus.cancelled
    db.commit()
    db.refresh(booking)
    return booking


def topup_wallet(db: Session, user_id: int, amount: float) -> User:
    """Simulate a wallet top-up (no real payment processor)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.wallet_balance = round(user.wallet_balance + amount, 2)
    db.commit()
    db.refresh(user)
    return user
