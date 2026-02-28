from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.models import BookingProposalStatus


# --- Chat Schemas -------------------------------------------------------------

class ChatCreate(BaseModel):
    receiver_id: int
    job_id: Optional[int] = None
    initial_message: Optional[str] = None


class ChatOut(BaseModel):
    id: int
    initiator_id: int
    receiver_id: int
    job_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ChatWithParticipants(BaseModel):
    id: int
    initiator_id: int
    receiver_id: int
    job_id: Optional[int]
    initiator_name: str
    receiver_name: str
    last_message: Optional[str]
    last_message_time: Optional[datetime]
    unread_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Message Schemas ----------------------------------------------------------

class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    content: str
    is_read: bool
    created_at: datetime
    sender_name: str

    model_config = {"from_attributes": True}


# --- Booking Proposal Schemas -------------------------------------------------

class BookingProposalCreate(BaseModel):
    job_id: int
    worker_id: int
    client_id: int
    agreed_rate: float
    duration_hours: float
    notes: Optional[str] = None


class BookingProposalOut(BaseModel):
    id: int
    chat_id: int
    job_id: int
    proposed_by_id: int
    worker_id: int
    client_id: int
    agreed_rate: float
    duration_hours: float
    total_amount: float
    notes: Optional[str]
    status: BookingProposalStatus
    client_accepted: bool
    worker_accepted: bool
    created_at: datetime
    accepted_at: Optional[datetime]
    booking_id: Optional[int]

    model_config = {"from_attributes": True}


class BookingProposalAccept(BaseModel):
    accept: bool


# --- Review Schemas -----------------------------------------------------------

class ReviewCreate(BaseModel):
    rating: int  # 1-5
    comment: Optional[str] = None
    is_anonymous: bool = False


class ReviewOut(BaseModel):
    id: int
    booking_id: int
    worker_profile_id: int
    worker_id: int
    reviewer_id: int
    rating: int
    comment: Optional[str]
    is_anonymous: bool
    reviewer_name: Optional[str]  # Only if not anonymous
    created_at: datetime

    model_config = {"from_attributes": True}

