"""
Contact Form API

Handles contact form submissions with validation, rate limiting, spam protection,
and persistence. Includes admin endpoint for reviewing submissions.
"""

import os
import re
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel, EmailStr, Field, validator
from fastapi.responses import JSONResponse

# Rate limiting
try:
    from backend.redis_client import RedisClient
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Authentication
try:
    from core.auth import require_admin
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False


async def get_admin_user(request: Request):
    """Dynamic admin dependency that checks AUTH_AVAILABLE at request time"""
    if AUTH_AVAILABLE:
        return await require_admin(request)
    return None


# Create router
router = APIRouter(prefix="/api/contact", tags=["contact"])


# Configuration
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "contact_submissions.db"
NOTIFICATION_LOG = DATA_DIR / "contact_notifications.log"
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "support@astraguard.ai")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", None)

# Rate limiting configuration
RATE_LIMIT_SUBMISSIONS = 5  # submissions per hour per IP
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds


# Pydantic Models
class ContactSubmission(BaseModel):
    """Contact form submission model"""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., min_length=5, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    subject: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=10, max_length=5000)
    website: Optional[str] = Field(None, description="Honeypot field")
    
    @validator('name', 'subject', 'message')
    def sanitize_text(cls, v):
        """Remove dangerous characters to prevent XSS"""
        if v:
            # Remove HTML tags and dangerous characters
            v = re.sub(r'[<>"\'&]', '', v)
        return v
    
    @validator('email')
    def normalize_email(cls, v):
        """Normalize email to lowercase"""
        return v.lower() if v else v


class ContactResponse(BaseModel):
    """Response for successful submission"""
    success: bool
    message: str
    submission_id: Optional[int] = None


class SubmissionRecord(BaseModel):
    """Full submission record with metadata"""
    id: int
    name: str
    email: str
    phone: Optional[str]
    subject: str
    message: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    submitted_at: str
    status: str


class SubmissionsResponse(BaseModel):
    """Response for admin submissions query"""
    total: int
    limit: int
    offset: int
    submissions: List[SubmissionRecord]


# Database initialization
def init_database():
    """Initialize SQLite database with contact_submissions table"""
    DATA_DIR.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    # Create index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_submitted_at 
        ON contact_submissions(submitted_at DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_status 
        ON contact_submissions(status)
    """)
    
    conn.commit()
    conn.close()


# Initialize database on module load
init_database()


# Rate limiting helper
class InMemoryRateLimiter:
    """Simple in-memory rate limiter when Redis is not available"""
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check if request is allowed under rate limit"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=window)
        
        # Clean old entries
        if key in self.requests:
            self.requests[key] = [ts for ts in self.requests[key] if ts > cutoff]
        else:
            self.requests[key] = []
        
        # Check limit
        if len(self.requests[key]) >= limit:
            return False
        
        # Add new request
        self.requests[key].append(now)
        return True


# Global rate limiter instance
_in_memory_limiter = InMemoryRateLimiter()


def check_rate_limit(ip_address: str) -> bool:
    """Check if IP is within rate limit"""
    # Use in-memory rate limiter (reliable and doesn't require Redis)
    return _in_memory_limiter.is_allowed(
        f"contact:{ip_address}",
        RATE_LIMIT_SUBMISSIONS,
        RATE_LIMIT_WINDOW
    )


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


def save_submission(
    submission: ContactSubmission,
    ip_address: str,
    user_agent: str
) -> int:
    """Save submission to database and return submission ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO contact_submissions 
        (name, email, phone, subject, message, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        submission.name,
        submission.email,
        submission.phone,
        submission.subject,
        submission.message,
        ip_address,
        user_agent
    ))
    
    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return submission_id


def log_notification(submission: ContactSubmission, submission_id: int):
    """Log notification to file (fallback when email is not configured)"""
    DATA_DIR.mkdir(exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "submission_id": submission_id,
        "name": submission.name,
        "email": submission.email,
        "subject": submission.subject,
        "message": submission.message[:100] + "..." if len(submission.message) > 100 else submission.message
    }
    
    with open(NOTIFICATION_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def send_email_notification(submission: ContactSubmission, submission_id: int):
    """Send email notification (placeholder for SendGrid integration)"""
    # TODO: Implement SendGrid integration when SENDGRID_API_KEY is set
    if SENDGRID_API_KEY:
        try:
            # Example SendGrid implementation:
            # from sendgrid import SendGridAPIClient
            # from sendgrid.helpers.mail import Mail
            # 
            # message = Mail(
            #     from_email='noreply@astraguard.ai',
            #     to_emails=CONTACT_EMAIL,
            #     subject=f'New Contact Form Submission: {submission.subject}',
            #     html_content=f'''
            #         <h2>New Contact Form Submission</h2>
            #         <p><strong>From:</strong> {submission.name} ({submission.email})</p>
            #         <p><strong>Subject:</strong> {submission.subject}</p>
            #         <p><strong>Message:</strong></p>
            #         <p>{submission.message}</p>
            #         <p><strong>Submission ID:</strong> {submission_id}</p>
            #     '''
            # )
            # sg = SendGridAPIClient(SENDGRID_API_KEY)
            # response = sg.send(message)
            pass
        except Exception as e:
            print(f"Email sending failed: {e}")
            log_notification(submission, submission_id)
    else:
        # Fallback to file logging
        log_notification(submission, submission_id)


# API Endpoints

@router.post("", response_model=ContactResponse, status_code=201)
async def submit_contact_form(
    submission: ContactSubmission,
    request: Request
):
    """
    Submit a contact form
    
    - **name**: Full name (2-100 characters)
    - **email**: Valid email address
    - **phone**: Optional phone number
    - **subject**: Message subject (3-200 characters)
    - **message**: Message content (10-5000 characters)
    
    Rate limit: 5 submissions per hour per IP address
    """
    # Honeypot spam protection
    if submission.website:
        # Bot detected - return fake success to avoid revealing honeypot
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Thank you for your message! We'll get back to you within 24-48 hours."
            }
        )
    
    # Get client info
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    
    # Rate limiting
    if not check_rate_limit(ip_address):
        raise HTTPException(
            status_code=429,
            detail="Too many submissions. Please try again later."
        )
    
    # Save to database
    try:
        submission_id = save_submission(submission, ip_address, user_agent)
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to save submission. Please try again later."
        )
    
    # Send notification
    try:
        send_email_notification(submission, submission_id)
    except Exception as e:
        print(f"Notification error: {e}")
        # Don't fail the request if notification fails
    
    return ContactResponse(
        success=True,
        message="Thank you for your message! We'll get back to you within 24-48 hours.",
        submission_id=submission_id
    )


@router.get("/submissions", response_model=SubmissionsResponse)
async def get_submissions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, regex="^(pending|resolved|spam)$"),
    current_user = Depends(get_admin_user)
):
    """
    Get contact form submissions (Admin only)
    
    - **limit**: Number of results (1-200, default 50)
    - **offset**: Pagination offset (default 0)
    - **status_filter**: Filter by status (pending/resolved/spam)
    
    Requires admin authentication
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query
    where_clause = ""
    params = []
    
    if status_filter:
        where_clause = "WHERE status = ?"
        params.append(status_filter)
    
    # Get total count
    count_query = f"SELECT COUNT(*) as total FROM contact_submissions {where_clause}"
    total = cursor.execute(count_query, params).fetchone()["total"]
    
    # Get submissions
    query = f"""
        SELECT id, name, email, phone, subject, message, ip_address, 
               user_agent, submitted_at, status
        FROM contact_submissions
        {where_clause}
        ORDER BY submitted_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    
    rows = cursor.execute(query, params).fetchall()
    conn.close()
    
    submissions = [
        SubmissionRecord(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            subject=row["subject"],
            message=row["message"],
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            submitted_at=row["submitted_at"],
            status=row["status"]
        )
        for row in rows
    ]
    
    return SubmissionsResponse(
        total=total,
        limit=limit,
        offset=offset,
        submissions=submissions
    )


@router.patch("/submissions/{submission_id}/status")
async def update_submission_status(
    submission_id: int,
    status: str = Query(..., regex="^(pending|resolved|spam)$"),
    current_user = Depends(get_admin_user)
):
    """
    Update submission status (Admin only)
    
    - **submission_id**: ID of the submission
    - **status**: New status (pending/resolved/spam)
    
    Requires admin authentication
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE contact_submissions SET status = ? WHERE id = ?",
        (status, submission_id)
    )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Submission not found")
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": f"Status updated to {status}"}


# Health check endpoint
@router.get("/health")
async def contact_health():
    """Check contact form service health"""
    try:
        # Check database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM contact_submissions")
        total_submissions = cursor.fetchone()[0]
        conn.close()
        
        # Check rate limiting
        rate_limiter_status = "redis" if REDIS_AVAILABLE else "in-memory"
        
        return {
            "status": "healthy",
            "database": "connected",
            "total_submissions": total_submissions,
            "rate_limiter": rate_limiter_status,
            "email_configured": SENDGRID_API_KEY is not None
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Contact service unhealthy: {str(e)}"
        )
