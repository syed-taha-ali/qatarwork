from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    client = "client"
    worker = "worker"
    admin = "admin"


class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    disputed = "disputed"


class PaymentStatus(str, enum.Enum):
    unpaid = "unpaid"
    held = "held"          # funds in escrow
    released = "released"  # payment released to worker
    refunded = "refunded"


class SkillCategory(str, enum.Enum):
    # Skilled Trades
    general_handyman = "general_handyman"
    locksmith = "locksmith"
    electrician = "electrician"
    plumber = "plumber"
    carpenter = "carpenter"
    hvac_tech = "hvac_tech"
    painter = "painter"
    gardener = "gardener"
    chef = "chef"
    exterminator = "exterminator"
    # Care & Personal Support
    maid = "maid"
    nanny = "nanny"
    nurse = "nurse"
    babysitter = "babysitter"
    pet_sitter = "pet_sitter"
    # Other
    other = "other"


class BookingProposalStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


class ReviewRating(int, enum.Enum):
    one_star = 1
    two_stars = 2
    three_stars = 3
    four_stars = 4
    five_stars = 5


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(SAEnum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    wallet_balance = Column(Float, default=0.0)  # simulated wallet
    profile_picture = Column(String(500), nullable=True)  # Path to uploaded image
    email_verified = Column(Boolean, default=False)
    verification_code = Column(String(10), nullable=True)
    verification_code_expires = Column(DateTime(timezone=True), nullable=True)
    
    # Profile verification (admin-approved)
    verification_status = Column(String(20), default="unverified")  # unverified, pending, approved, rejected
    verification_applied_at = Column(DateTime(timezone=True), nullable=True)
    verification_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    verification_reviewed_by = Column(Integer, nullable=True)  # admin user_id
    verification_rejection_reason = Column(Text, nullable=True)
    
    # Message encryption keys (RSA key pair for each user)
    public_key = Column(Text, nullable=True)  # RSA public key (for encrypting messages TO this user)
    private_key_encrypted = Column(Text, nullable=True)  # RSA private key (encrypted with user's password hash)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    worker_profile = relationship("WorkerProfile", back_populates="user", uselist=False)
    jobs_posted = relationship("Job", back_populates="client", foreign_keys="Job.client_id")
    bookings_as_client = relationship("Booking", back_populates="client", foreign_keys="Booking.client_id")
    bookings_as_worker = relationship("Booking", back_populates="worker", foreign_keys="Booking.worker_id")
    transactions = relationship("Transaction", back_populates="user")
    chats_initiated = relationship("Chat", back_populates="initiator", foreign_keys="Chat.initiator_id")
    chats_received = relationship("Chat", back_populates="receiver", foreign_keys="Chat.receiver_id")
    messages_sent = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    reviews_written = relationship("Review", back_populates="reviewer", foreign_keys="Review.reviewer_id")
    reviews_received = relationship("Review", back_populates="worker", foreign_keys="Review.worker_id")
    verification_history = relationship("VerificationHistory", back_populates="user", foreign_keys="VerificationHistory.user_id", order_by="desc(VerificationHistory.created_at)")


class VerificationHistory(Base):
    """Track all verification application attempts for complete audit trail."""
    __tablename__ = "verification_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Application details
    applied_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status = Column(String(20), nullable=False)  # submitted, approved, rejected
    
    # Review details (if reviewed)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # admin user_id
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="verification_history", foreign_keys=[user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])


class WorkerProfile(Base):
    __tablename__ = "worker_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    skill_category = Column(SAEnum(SkillCategory), nullable=False)  # Back to single skill
    hourly_rate = Column(Float, nullable=False)
    bio = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    years_experience = Column(Integer, default=0)
    is_available = Column(Boolean, default=True)
    total_jobs_completed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="worker_profile")
    bookings = relationship("Booking", back_populates="worker_profile", foreign_keys="Booking.worker_profile_id")
    reviews = relationship("Review", back_populates="worker_profile")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    skill_required = Column(SAEnum(SkillCategory), nullable=False)
    duration_hours = Column(Float, nullable=False)
    budget = Column(Float, nullable=False)
    location = Column(String(200), nullable=False)
    is_open = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    client = relationship("User", back_populates="jobs_posted", foreign_keys=[client_id])
    booking = relationship("Booking", back_populates="job", uselist=False)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    worker_profile_id = Column(Integer, ForeignKey("worker_profiles.id"), nullable=False)

    # Financials
    agreed_rate = Column(Float, nullable=False)       # hourly rate agreed
    duration_hours = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)       # agreed_rate * duration_hours
    platform_fee_percent = Column(Float, nullable=False)
    client_fee = Column(Float, nullable=False)         # client pays this extra
    worker_fee = Column(Float, nullable=False)         # deducted from worker payout
    worker_payout = Column(Float, nullable=False)      # total_amount - worker_fee
    client_total = Column(Float, nullable=False)       # total_amount + client_fee

    status = Column(SAEnum(BookingStatus), default=BookingStatus.pending)
    payment_status = Column(SAEnum(PaymentStatus), default=PaymentStatus.unpaid)

    # Completion tracking - both parties must confirm
    client_confirmed_complete = Column(Boolean, default=False)
    worker_confirmed_complete = Column(Boolean, default=False)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    job = relationship("Job", back_populates="booking")
    client = relationship("User", back_populates="bookings_as_client", foreign_keys=[client_id])
    worker = relationship("User", back_populates="bookings_as_worker", foreign_keys=[worker_id])
    worker_profile = relationship("WorkerProfile", back_populates="bookings", foreign_keys=[worker_profile_id])
    transactions = relationship("Transaction", back_populates="booking")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # debit / credit / fee
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    booking = relationship("Booking", back_populates="transactions")
    user = relationship("User", back_populates="transactions")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    initiator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)  # Optional: chat about specific job
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    initiator = relationship("User", back_populates="chats_initiated", foreign_keys=[initiator_id])
    receiver = relationship("User", back_populates="chats_received", foreign_keys=[receiver_id])
    job = relationship("Job")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    booking_proposals = relationship("BookingProposal", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)  # Encrypted for recipient
    content_sender = Column(Text, nullable=True)  # Encrypted for sender (so they can see their own messages)
    is_encrypted = Column(Boolean, default=True)  # Flag for encryption
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="messages_sent", foreign_keys=[sender_id])


class BookingProposal(Base):
    __tablename__ = "booking_proposals"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    proposed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Financial details
    agreed_rate = Column(Float, nullable=False)
    duration_hours = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Status tracking
    status = Column(SAEnum(BookingProposalStatus), default=BookingProposalStatus.pending)
    client_accepted = Column(Boolean, default=False)
    worker_accepted = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)  # Set when both accept

    # Relationships
    chat = relationship("Chat", back_populates="booking_proposals")
    job = relationship("Job")
    proposed_by = relationship("User", foreign_keys=[proposed_by_id])
    worker = relationship("User", foreign_keys=[worker_id])
    client = relationship("User", foreign_keys=[client_id])
    booking = relationship("Booking")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), unique=True, nullable=False)  # One review per booking
    worker_profile_id = Column(Integer, ForeignKey("worker_profiles.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Worker being reviewed
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Client who wrote review
    
    rating = Column(Integer, nullable=False)  # 1-5 stars
    comment = Column(Text, nullable=True)
    is_anonymous = Column(Boolean, default=False)  # Hide reviewer name if true
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    booking = relationship("Booking")
    worker_profile = relationship("WorkerProfile", back_populates="reviews")
    worker = relationship("User", back_populates="reviews_received", foreign_keys=[worker_id])
    reviewer = relationship("User", back_populates="reviews_written", foreign_keys=[reviewer_id])

