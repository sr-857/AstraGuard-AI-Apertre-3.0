"""
Contact Form API

Handles contact form submissions with validation, rate limiting, spam protection,
and persistence. Includes admin endpoint for reviewing submissions.

Optimized for async I/O performance using aiosqlite and connection pooling.
"""

import os
import re
import logging
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Any, Union
from functools import lru_cache
from collections import deque
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel, EmailStr, Field, field_validator, ValidationError as PydanticValidationError
from fastapi.responses import JSONResponse
import aiosqlite
import aiofiles


# Declare variables BEFORE try block
REDIS_AVAILABLE: bool
AUTH_AVAILABLE: bool

try:
    from backend.redis_client import RedisClient
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from core.auth import require_admin
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False


logger: logging.Logger = logging.getLogger(__name__)


if AUTH_AVAILABLE:
    async def get_admin_user(user: Any = Depends(require_admin)) -> Any:
        return user
else:
    async def get_admin_user(user: Any = None) -> Any:
        return None


router: APIRouter = APIRouter(prefix="/api/contact", tags=["contact"])

DATA_DIR: Path = Path("data")
DB_PATH: Path = DATA_DIR / "contact_submissions.db"
NOTIFICATION_LOG: Path = DATA_DIR / "contact_notifications.log"
CONTACT_EMAIL: str = os.getenv("CONTACT_EMAIL", "support@astraguard.ai")
SENDGRID_API_KEY: Optional[str] = os.getenv("SENDGRID_API_KEY", None)

_raw_trusted: str = os.getenv("TRUSTED_PROXIES", "")
TRUSTED_PROXIES: set[str] = {ip.strip() for ip in _raw_trusted.split(",") if ip.strip()}

RATE_LIMIT_SUBMISSIONS: int = 5
RATE_LIMIT_WINDOW: int = 3600

# Database connection pool
DB_POOL_SIZE: int = 10
_db_connection_pool: deque = deque(maxlen=DB_POOL_SIZE)
_pool_lock: asyncio.Lock = asyncio.Lock()

# Batch logging buffer
_log_buffer: deque = deque()
_log_buffer_lock: asyncio.Lock = asyncio.Lock()
_log_buffer_size: int = 10


class ContactSubmission(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name (2-100 characters)")
    email: EmailStr = Field(..., min_length=5, max_length=100, description="Valid email address")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number (optional)")
    subject: str = Field(..., min_length=3, max_length=200, description="Subject line (3-200 characters)")
    message: str = Field(..., min_length=10, max_length=5000, description="Message content (10-5000 characters)")
    website: Optional[str] = Field(None, description="Honeypot field - leave empty")

    @field_validator("name", "subject", "message", mode="before")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        """Remove potentially dangerous HTML/script characters for XSS protection"""
        if v:
            # Remove HTML tags and dangerous characters
            v = re.sub(r'[<>"\'&]', "", v)
            # Remove any script-like patterns
            v = re.sub(r'(?i)(javascript|onerror|onload|onclick):', "", v)
        return v

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase for consistency"""
        return v.lower() if v else v
    
    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format if provided"""
        if v:
            # Remove common formatting characters
            cleaned = re.sub(r'[\s\-\(\)\.]', '', v)
            # Check if it contains only digits and optional + prefix
            if not re.match(r'^\+?\d{7,15}$', cleaned):
                raise ValueError("Phone number must contain 7-15 digits with optional + prefix")
        return v


class ContactResponse(BaseModel):
    success: bool
    message: str
    submission_id: Optional[int] = None
    rate_limit_info: Optional[dict[str, Any]] = None


class SubmissionRecord(BaseModel):
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
    total: int
    limit: int
    offset: int
    submissions: List[SubmissionRecord]


def init_database() -> None:
    """Initialize contact submissions database with error handling."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
    except OSError as e:
        logger.error(
            "Failed to create data directory",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "directory": str(DATA_DIR),
                "operation": "mkdir"
            },
            exc_info=True
        )
        raise RuntimeError(f"Cannot create data directory: {e}") from e

    try:
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
        
        logger.info("Contact database initialized successfully", db_path=str(DB_PATH))
        
    except sqlite3.Error as e:
        logger.error(
            "Failed to initialize contact database",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "db_path": str(DB_PATH),
                "operation": "init_database"
            },
            exc_info=True
        )
        raise RuntimeError(f"Cannot initialize contact database: {e}") from e
    except Exception as e:
        logger.error(
            "Unexpected error initializing contact database",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "db_path": str(DB_PATH),
                "operation": "init_database"
            },
            exc_info=True
        )
        raise


class InMemoryRateLimiter:
    """
    Optimized in-memory rate limiter with efficient cleanup strategy.
    Uses deque for O(1) append operations and periodic cleanup.
    """

    def __init__(self) -> None:
        self.requests: dict[str, deque[datetime]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup: datetime = datetime.now()
        self._cleanup_interval: int = 300  # Run cleanup every 5 minutes

    async def _periodic_cleanup(self, window: int) -> None:
        """Periodically clean up expired entries to prevent memory bloat"""
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() < self._cleanup_interval:
            return
            
        cutoff = now - timedelta(seconds=window)
        keys_to_delete = []
        
        for key, timestamps in self.requests.items():
            # Remove expired timestamps
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            
            if not timestamps:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.requests[key]
        
        self._last_cleanup = now

    async def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, dict[str, Any]]:
        """
        Check if request is allowed and return rate limit metadata.
        
        Returns:
            tuple: (is_allowed, metadata) where metadata contains:
                - remaining: requests remaining in current window
                - reset_at: when the rate limit window resets
                - limit: total requests allowed per window
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=window)

            if key in self.requests:
                # Efficient cleanup using deque
                while self.requests[key] and self.requests[key][0] <= cutoff:
                    self.requests[key].popleft()
                
                if not self.requests[key]:
                    del self.requests[key]
            
            if key not in self.requests:
                self.requests[key] = deque()

            current_count = len(self.requests[key])
            is_allowed = current_count < limit
            
            # Calculate reset time (oldest request + window)
            reset_at = None
            if self.requests[key]:
                oldest = self.requests[key][0]
                reset_at = (oldest + timedelta(seconds=window)).isoformat()
            
            metadata = {
                "limit": limit,
                "remaining": max(0, limit - current_count - (1 if is_allowed else 0)),
                "reset_at": reset_at,
                "window_seconds": window
            }

            if is_allowed:
                self.requests[key].append(now)

            # Run periodic cleanup
            await self._periodic_cleanup(window)

            return is_allowed, metadata


# Initialize database and limiter
init_database()
_in_memory_limiter: InMemoryRateLimiter = InMemoryRateLimiter()


async def get_db_connection() -> aiosqlite.Connection:
    """Get a database connection from the pool or create a new one"""
    async with _pool_lock:
        if _db_connection_pool:
            return _db_connection_pool.popleft()
    
    # Create new connection if pool is empty
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


async def return_db_connection(conn: aiosqlite.Connection) -> None:
    """Return a database connection to the pool"""
    async with _pool_lock:
        if len(_db_connection_pool) < DB_POOL_SIZE:
            _db_connection_pool.append(conn)
        else:
            await conn.close()


@lru_cache(maxsize=128)
def validate_and_normalize_email(email: str) -> str:
    """Cached email validation and normalization"""
    return email.lower()


async def flush_log_buffer() -> None:
    """Flush buffered log entries to disk"""
    if not _log_buffer:
        return
    
    async with _log_buffer_lock:
        if not _log_buffer:
            return
            
        entries = list(_log_buffer)
        _log_buffer.clear()
    
    try:
        async with aiofiles.open(NOTIFICATION_LOG, "a") as f:
            await f.write("\n".join(json.dumps(entry) for entry in entries) + "\n")
    except Exception as e:
        logger.error(f"Failed to flush log buffer: {e}")


async def check_rate_limit(ip_address: str) -> tuple[bool, dict[str, Any]]:
    """Check rate limit and return status with metadata"""
    return await _in_memory_limiter.is_allowed(
        f"contact:{ip_address}",
        RATE_LIMIT_SUBMISSIONS,
        RATE_LIMIT_WINDOW,
    )


@lru_cache(maxsize=256)
def get_cached_trusted_proxy_check(ip: str) -> bool:
    """Cached check for trusted proxies"""
    return ip in TRUSTED_PROXIES


def get_client_ip(request: Request) -> str:
    """Optimized IP extraction with cached proxy checking"""
    direct_ip: str = "unknown"
    if request.client:
        direct_ip = request.client.host

    if get_cached_trusted_proxy_check(direct_ip):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

    return direct_ip


async def save_submission(
    submission: ContactSubmission,
    ip_address: str,
    user_agent: str,
) -> Optional[int]:
    """Save contact submission to database with error handling."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO contact_submissions
                    (name, email, phone, subject, message, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission.name,
                    submission.email,
                    submission.phone,
                    submission.subject,
                    submission.message,
                    ip_address,
                    user_agent,
                ),
            )
            await conn.commit()
            submission_id = cursor.lastrowid
            
            logger.info(
                "Contact submission saved",
                extra={
                    "submission_id": submission_id,
                    "email": submission.email,
                    "ip_address": ip_address
                }
            )
            
            return submission_id
            
    except aiosqlite.IntegrityError as e:
        logger.error(
            "Database integrity error saving submission",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "email": submission.email,
                "ip_address": ip_address,
                "operation": "save_submission"
            },
            exc_info=True
        )
        raise
    except aiosqlite.OperationalError as e:
        logger.error(
            "Database operational error (locked or inaccessible)",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "db_path": str(DB_PATH),
                "email": submission.email,
                "operation": "save_submission"
            },
            exc_info=True
        )
        raise
    except aiosqlite.Error as e:
        logger.error(
            "Database error saving submission",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "email": submission.email,
                "ip_address": ip_address,
                "operation": "save_submission"
            },
            exc_info=True
        )
        raise


async def log_notification(
    submission: ContactSubmission,
    submission_id: Optional[int],
) -> None:
    """Log notification to file with error handling."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "submission_id": submission_id,
        "name": submission.name,
        "email": submission.email,
        "subject": submission.subject,
        "message": (
            submission.message[:100] + "..."
            if len(submission.message) > 100
            else submission.message
        ),
    }

    try:
        async with aiofiles.open(NOTIFICATION_LOG, "a") as f:
            await f.write(json.dumps(log_entry) + "\n")
            
        logger.debug(
            "Notification logged to file",
            extra={
                "submission_id": submission_id,
                "log_file": str(NOTIFICATION_LOG)
            }
        )
        
    except PermissionError as e:
        logger.error(
            "Permission denied writing notification log",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "log_file": str(NOTIFICATION_LOG),
                "submission_id": submission_id,
                "operation": "log_notification"
            },
            exc_info=True
        )
        raise
    except OSError as e:
        logger.error(
            "I/O error writing notification log (disk full or inaccessible)",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "log_file": str(NOTIFICATION_LOG),
                "submission_id": submission_id,
                "operation": "log_notification"
            },
            exc_info=True
        )
        raise


async def send_email_notification(submission: ContactSubmission, submission_id: Optional[int]) -> None:

    """Send email notification (placeholder for SendGrid integration)"""
    # TODO: Implement SendGrid integration when SENDGRID_API_KEY is set
    if SENDGRID_API_KEY:
        try:
            pass
        except OSError as e:
            logger.warning(
                "SendGrid send failed (network/IO error), falling back to file log",
                extra={
                    "error_type": type(e).__name__,
                    "operation": "send_email",
                    "submission_id": submission_id,
                    "email": submission.email
                },
                exc_info=True
            )
            await log_notification(submission, submission_id)
        except Exception as e:
            logger.warning(
                "SendGrid send failed (unexpected), falling back to file log",
                extra={
                    "error_type": type(e).__name__,
                    "operation": "send_email",
                    "submission_id": submission_id,
                    "email": submission.email
                },
                exc_info=True
            )
            await log_notification(submission, submission_id)
    else:
        await log_notification(submission, submission_id)

@router.post("", response_model=ContactResponse, status_code=201)
async def submit_contact_form(
    submission: ContactSubmission,
    request: Request,
) -> Union[JSONResponse, ContactResponse]:
    """
    Submit a contact form with comprehensive validation.
    
    Validates:
    - Email format (RFC 5322 compliant)
    - Message content sanitization (XSS protection)
    - Rate limiting per IP address
    - Spam detection via honeypot field
    
    Returns:
    - 201: Successfully created submission
    - 400: Validation error with detailed message
    - 429: Rate limit exceeded
    - 500: Server error
    """

    # Honeypot spam detection
    if submission.website:
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Thank you for your message! We'll get back to you within 24-48 hours.",
            },
        )

    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")

    # Check rate limit and get metadata
    is_allowed, rate_limit_metadata = await check_rate_limit(ip_address)
    
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": "Too many submissions. Please try again later.",
                "rate_limit": rate_limit_metadata
            },
        )

    try:
        submission_id = await save_submission(submission, ip_address, user_agent)
    except aiosqlite.Error as e:
        logger.error(
            "Database save failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "ip_address": ip_address,
                "email": submission.email,
                "subject": submission.subject,
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save submission. Please try again later.",
        )
    except Exception as e:
        logger.error(
            "Unexpected database error",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "ip_address": ip_address,
                "email": submission.email,
            },
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later.",
        )

    try:
        await send_email_notification(submission, submission_id)
    except OSError as e:
        logger.warning(
            "Notification failed due to I/O error but submission was saved",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "submission_id": submission_id,
                "email": submission.email,
                "subject": submission.subject,
                "operation": "send_notification"
            },
            exc_info=True
        )
    except Exception as e:
        logger.warning(
            "Notification failed (unexpected) but submission was saved",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "submission_id": submission_id,
                "email": submission.email,
                "subject": submission.subject,
                "operation": "send_notification"
            },
            exc_info=True
        )


    return ContactResponse(
        success=True,
        message="Thank you for your message! We'll get back to you within 24-48 hours.",
        submission_id=submission_id,
        rate_limit_info=rate_limit_metadata,
    )


@router.get("/submissions", response_model=SubmissionsResponse)
async def get_submissions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, pattern="^(pending|resolved|spam)$"),
    current_user: Any = Depends(get_admin_user),
) -> SubmissionsResponse:
    """Get contact submissions with pagination and filtering."""
    where_clause = ""
    params: list[Any] = []

    if status_filter:
        where_clause = "WHERE status = ?"
        params.append(status_filter)

    count_query = f"SELECT COUNT(*) AS total FROM contact_submissions {where_clause}"  # nosec B608
    select_query = f"""
        SELECT id, name, email, phone, subject, message,
               ip_address, user_agent, submitted_at, status
        FROM contact_submissions
        {where_clause}
        ORDER BY submitted_at DESC
        LIMIT ? OFFSET ?
    """

    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row

            async with conn.execute(count_query, params) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=500, detail="Failed to count submissions")
                total: int = row["total"]

            async with conn.execute(select_query, [*params, limit, offset]) as cursor:
                rows = await cursor.fetchall()

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
                status=row["status"],
            )
            for row in rows
        ]

        return SubmissionsResponse(
            total=total,
            limit=limit,
            offset=offset,
            submissions=submissions,
        )
        
    except aiosqlite.OperationalError as e:
        logger.error(
            "Database operational error fetching submissions",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "db_path": str(DB_PATH),
                "limit": limit,
                "offset": offset,
                "operation": "get_submissions"
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable"
        )
    except aiosqlite.Error as e:
        logger.error(
            "Database error fetching submissions",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "db_path": str(DB_PATH),
                "operation": "get_submissions"
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch submissions"
        )
    except HTTPException:
        # Re-raise HTTP exceptions (500 from count query)
        raise
    except Exception as e:
        logger.error(
            "Unexpected error fetching submissions",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "get_submissions"
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred"
        )


@router.patch("/submissions/{submission_id}/status")
async def update_submission_status(
    submission_id: int,
    status: str = Query(..., pattern="^(pending|resolved|spam)$"),
    current_user: Any = Depends(get_admin_user),
) -> dict[str, Any]:
    """Update submission status with error handling."""
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(
                "UPDATE contact_submissions SET status = ? WHERE id = ?",
                (status, submission_id),
            )
            await conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Submission not found")

        logger.info(
            "Submission status updated",
            extra={
                "submission_id": submission_id,
                "new_status": status
            }
        )

        return {"success": True, "message": f"Status updated to {status}"}
        
    except HTTPException:
        # Re-raise HTTP exceptions (404)
        raise
    except aiosqlite.OperationalError as e:
        logger.error(
            "Database operational error updating submission status",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "submission_id": submission_id,
                "status": status,
                "operation": "update_submission_status"
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable"
        )
    except aiosqlite.Error as e:
        logger.error(
            "Database error updating submission status",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "submission_id": submission_id,
                "status": status,
                "operation": "update_submission_status"
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update submission status"
        )
    except Exception as e:
        logger.error(
            "Unexpected error updating submission status",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "submission_id": submission_id,
                "operation": "update_submission_status"
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred"
        )


@router.get("/health")
async def contact_health() -> dict[str, Any]:
    """Health check with connection pooling and cached status"""
    try:
        conn = await get_db_connection()
        try:
            async with conn.execute(
                "SELECT COUNT(*) FROM contact_submissions"
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=503, detail="Health check query failed")
                total_submissions: int = row[0]
        finally:
            await return_db_connection(conn)

        rate_limiter_status = "redis" if REDIS_AVAILABLE else "in-memory"

        return {
            "status": "healthy",
            "database": "connected",
            "total_submissions": total_submissions,
            "rate_limiter": rate_limiter_status,
            "email_configured": SENDGRID_API_KEY is not None,
            "connection_pool_size": len(_db_connection_pool),
            "log_buffer_size": len(_log_buffer),
        }

    except aiosqlite.Error as e:
        logger.error(
            "Database health check failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "db_path": str(DB_PATH),
            },
        )
        raise HTTPException(status_code=503, detail="Database connection failed")

    except Exception as e:
        logger.error(
            "Health check failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "operation": "health_check",
                "db_path": str(DB_PATH)
            },
            exc_info=True
        )
        raise HTTPException(status_code=503, detail="Service health check failed")


@router.get("/pool-health")
async def pool_health() -> dict[str, Any]:
    """
    Get connection pool health statistics.
    
    Returns pool metrics including active connections, idle connections,
    total created, timeouts, and average wait time.
    """
    if not is_pool_enabled():
        return {
            "status": "disabled",
            "message": "Connection pooling is not enabled"
        }
    
    stats = await get_pool_stats()
    
    if stats is None:
        raise HTTPException(
            status_code=503,
            detail="Pool statistics unavailable"
        )
    
    return {
        "status": "healthy",
        "pool": {
            "active_connections": stats.active_connections,
            "idle_connections": stats.idle_connections,
            "total_connections": stats.total_connections,
            "max_size": stats.max_size,
            "total_created": stats.total_created,
            "total_acquisitions": stats.total_acquisitions,
            "total_releases": stats.total_releases,
            "total_timeouts": stats.total_timeouts,
            "total_errors": stats.total_errors,
            "average_wait_time_ms": round(stats.average_wait_time * 1000, 2),
        }
    }
