from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from app.models.models import UserRole, BookingStatus, PaymentStatus, SkillCategory


# --- Auth / User Schemas ------------------------------------------------------

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    role: UserRole

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str]
    role: UserRole
    wallet_balance: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: int
    full_name: str


# --- Worker Profile Schemas ---------------------------------------------------

class WorkerProfileCreate(BaseModel):
    skill_category: SkillCategory
    hourly_rate: float
    bio: Optional[str] = None
    location: Optional[str] = None
    years_experience: int = 0

    @field_validator("hourly_rate")
    @classmethod
    def rate_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Hourly rate must be positive")
        return v


class WorkerProfileUpdate(BaseModel):
    skill_category: Optional[SkillCategory] = None
    hourly_rate: Optional[float] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    years_experience: Optional[int] = None
    is_available: Optional[bool] = None


class WorkerProfileOut(BaseModel):
    id: int
    user_id: int
    skill_category: SkillCategory
    hourly_rate: float
    bio: Optional[str]
    location: Optional[str]
    years_experience: int
    is_available: bool
    total_jobs_completed: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkerWithUser(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str]
    worker_profile: Optional[WorkerProfileOut]

    model_config = {"from_attributes": True}


# --- Job Schemas --------------------------------------------------------------

class JobCreate(BaseModel):
    title: str
    description: str
    skill_required: SkillCategory
    duration_hours: float
    budget: float
    location: str

    @field_validator("duration_hours", "budget")
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    skill_required: Optional[SkillCategory] = None
    duration_hours: Optional[float] = None
    budget: Optional[float] = None
    location: Optional[str] = None
    is_open: Optional[bool] = None


class JobOut(BaseModel):
    id: int
    client_id: int
    title: str
    description: str
    skill_required: SkillCategory
    duration_hours: float
    budget: float
    location: str
    is_open: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Booking Schemas ----------------------------------------------------------

class BookingCreate(BaseModel):
    job_id: int
    worker_id: int
    notes: Optional[str] = None


class BookingOut(BaseModel):
    id: int
    job_id: int
    client_id: int
    worker_id: int
    agreed_rate: float
    duration_hours: float
    total_amount: float
    platform_fee_percent: float
    client_fee: float
    worker_fee: float
    worker_payout: float
    client_total: float
    status: BookingStatus
    payment_status: PaymentStatus
    notes: Optional[str]
    created_at: datetime
    confirmed_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


# --- Transaction Schemas ------------------------------------------------------

class TransactionOut(BaseModel):
    id: int
    booking_id: int
    user_id: int
    amount: float
    transaction_type: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Wallet / Top-up Schema ---------------------------------------------------

class WalletTopUp(BaseModel):
    amount: float

    @field_validator("amount")
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Top-up amount must be positive")
        return v


# --- Dashboard Schema ---------------------------------------------------------

class DashboardStats(BaseModel):
    total_jobs: int
    open_jobs: int
    total_bookings: int
    active_bookings: int
    wallet_balance: float
    total_earned: Optional[float] = None
    total_spent: Optional[float] = None
