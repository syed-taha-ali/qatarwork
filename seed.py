"""
Database Seeding Script
Populates the Qatar Labor platform database with sample data for development and testing.

This script creates:
- Admin user
- Client users
- Worker users with profiles and skills
- Sample jobs
- Sample reviews

Usage:
    python seed.py

Note: This will drop all existing tables and recreate them with fresh data.
"""
import os
import sys
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, engine, Base
from app.models.models import (
    User, WorkerProfile, Job, Review,
    UserRole, SkillCategory
)
import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        str: Bcrypt hashed password
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def seed_database():
    """
    Populate database with sample data.
    
    This function:
    1. Drops all existing tables
    2. Creates fresh tables
    3. Seeds with sample users, profiles, jobs, and reviews
    4. Generates encryption keys for all users
    """
    
    # Drop all tables and recreate (fresh start)
    logger.info("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    logger.info("  Creating all tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        logger.info("\n Creating users...")
        
        # Admin user
        admin = User(
            full_name="Admin",
            email="admin@gmail.com",
            hashed_password=hash_password("admin123"),
            phone="+97455005500",
            role=UserRole.admin,
            wallet_balance=0.0,
            profile_picture=None,
            email_verified=True,
            verification_status="approved"
        )
        
        # Create clients
        client1 = User(
            full_name="Ahmed Hassan",
            email="ahmed@client.com",
            hashed_password=hash_password("password123"),
            phone="+974 5555 1234",
            role=UserRole.client,
            wallet_balance=5000.0,
            profile_picture=None  # No picture yet
        )
        
        client2 = User(
            full_name="Sarah Al-Mansoori",
            email="sarah@client.com",
            hashed_password=hash_password("password123"),
            phone="+974 5555 5678",
            role=UserRole.client,
            wallet_balance=3000.0,
            profile_picture=None
        )
        
        # Create workers
        worker1 = User(
            full_name="Mohammed Ali",
            email="mohammed@worker.com",
            hashed_password=hash_password("password123"),
            phone="+974 5555 9876",
            role=UserRole.worker,
            wallet_balance=1200.0,
            profile_picture=None
        )
        
        worker2 = User(
            full_name="Fatima Ibrahim",
            email="fatima@worker.com",
            hashed_password=hash_password("password123"),
            phone="+974 5555 4321",
            role=UserRole.worker,
            wallet_balance=800.0,
            profile_picture=None
        )
        
        worker3 = User(
            full_name="Youssef Rahman",
            email="youssef@worker.com",
            hashed_password=hash_password("password123"),
            phone="+974 5555 8765",
            role=UserRole.worker,
            wallet_balance=2500.0,
            profile_picture=None
        )
        
        worker4 = User(
            full_name="Layla Hassan",
            email="layla@worker.com",
            hashed_password=hash_password("password123"),
            phone="+974 5555 2468",
            role=UserRole.worker,
            wallet_balance=1500.0,
            profile_picture=None
        )
        
        worker5 = User(
            full_name="Omar Abdullah",
            email="omar@worker.com",
            hashed_password=hash_password("password123"),
            phone="+974 5555 1357",
            role=UserRole.worker,
            wallet_balance=950.0,
            profile_picture=None
        )
        
        db.add_all([admin, client1, client2, worker1, worker2, worker3, worker4, worker5])
        db.commit()
        
        print(f" Created {2} clients and {5} workers")
        
        logger.info("\n Creating worker profiles...")
        
        # Worker 1: Plumber
        profile1 = WorkerProfile(
            user_id=worker1.id,
            skill_category=SkillCategory.plumber,
            hourly_rate=85.0,
            bio="Experienced plumber with 8 years in residential and commercial projects. Licensed and insured.",
            location="Doha",
            years_experience=8,
            is_available=True,
            total_jobs_completed=47
        )
        
        # Worker 2: Nanny
        profile2 = WorkerProfile(
            user_id=worker2.id,
            skill_category=SkillCategory.nanny,
            hourly_rate=60.0,
            bio="Certified childcare professional with pediatric first aid training. Patient and caring.",
            location="Al Wakra",
            years_experience=5,
            is_available=True,
            total_jobs_completed=32
        )
        
        # Worker 3: General Handyman
        profile3 = WorkerProfile(
            user_id=worker3.id,
            skill_category=SkillCategory.general_handyman,
            hourly_rate=70.0,
            bio="Jack of all trades! Can handle carpentry, painting, basic plumbing, and general repairs.",
            location="Doha",
            years_experience=10,
            is_available=True,
            total_jobs_completed=89
        )
        
        # Worker 4: Maid
        profile4 = WorkerProfile(
            user_id=worker4.id,
            skill_category=SkillCategory.maid,
            hourly_rate=55.0,
            bio="Professional housekeeping services. Detailed cleaning and organization.",
            location="Al Rayyan",
            years_experience=6,
            is_available=True,
            total_jobs_completed=54
        )
        
        # Worker 5: HVAC Technician
        profile5 = WorkerProfile(
            user_id=worker5.id,
            skill_category=SkillCategory.hvac_tech,
            hourly_rate=90.0,
            bio="HVAC specialist. Expert in AC installation and repair.",
            location="Lusail",
            years_experience=7,
            is_available=False,  # Currently unavailable
            total_jobs_completed=38
        )
        
        db.add_all([profile1, profile2, profile3, profile4, profile5])
        db.commit()
        
        print(f" Created {5} worker profiles")
        
        logger.info("\n Creating jobs...")
        
        job1 = Job(
            client_id=client1.id,
            title="Fix Leaking Kitchen Sink",
            description="Kitchen sink has been leaking for a week. Need urgent repair.",
            skill_required=SkillCategory.plumber,
            duration_hours=2.0,
            budget=200.0,
            location="Doha, West Bay",
            is_open=True
        )
        
        job2 = Job(
            client_id=client1.id,
            title="Install New Light Fixtures",
            description="Need to install 5 new LED light fixtures in living room and bedrooms.",
            skill_required=SkillCategory.electrician,
            duration_hours=3.0,
            budget=300.0,
            location="Doha, West Bay",
            is_open=True
        )
        
        job3 = Job(
            client_id=client2.id,
            title="Weekly House Cleaning",
            description="Looking for regular weekly cleaning service. 3-bedroom villa.",
            skill_required=SkillCategory.maid,
            duration_hours=4.0,
            budget=250.0,
            location="Al Wakra",
            is_open=True
        )
        
        job4 = Job(
            client_id=client2.id,
            title="Babysitting for Weekend",
            description="Need babysitter for 2 kids (ages 3 and 6) on Saturday evening.",
            skill_required=SkillCategory.babysitter,
            duration_hours=5.0,
            budget=350.0,
            location="Al Wakra",
            is_open=True
        )
        
        job5 = Job(
            client_id=client1.id,
            title="AC Repair - Not Cooling",
            description="AC unit stopped cooling properly. Need diagnosis and repair.",
            skill_required=SkillCategory.hvac_tech,
            duration_hours=2.0,
            budget=250.0,
            location="Doha, Al Sadd",
            is_open=False  # Already filled
        )
        
        db.add_all([job1, job2, job3, job4, job5])
        db.commit()
        
        print(f" Created {5} jobs")
        
        logger.info("\n" + "="*50)
        logger.info(" Database seeded successfully!")
        logger.info("="*50)
        logger.info("\n Summary:")
        print(f"  • {2} Clients")
        print(f"  • {5} Workers")
        print(f"  • {5} Jobs")
        logger.info("\n Login Credentials:")
        logger.info("  Clients:")
        logger.info("    • ahmed@client.com / password123")
        logger.info("    • sarah@client.com / password123")
        logger.info("  Workers:")
        logger.info("    • mohammed@worker.com / password123")
        logger.info("    • fatima@worker.com / password123")
        logger.info("    • youssef@worker.com / password123")
        logger.info("    • layla@worker.com / password123")
        logger.info("    • omar@worker.com / password123")
        logger.info("\n Server is ready to start!")
        
    except Exception as e:
        print(f"\nERROR: Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
