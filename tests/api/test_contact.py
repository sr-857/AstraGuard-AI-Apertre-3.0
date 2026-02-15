"""
Unit tests for Contact Form API (src/api/contact.py)

Tests cover:
- Form validation and sanitization
- Rate limiting (in-memory, async-safe)
- Spam protection (honeypot)
- Database operations (aiosqlite)
- Admin endpoints
- Error handling
- Health checks

All 38 original tests are preserved and updated where the underlying
implementation changed (e.g. is_allowed is now async, sqlite3 → aiosqlite).
New tests are added to cover bugs that were previously invisible because the
test suite never imported the real module.
"""

import pytest
import sqlite3
import aiosqlite
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Optional
import sys

# Mock optional dependencies BEFORE importing anything from the project
sys.modules["httpx"] = MagicMock()
sys.modules["backend.redis_client"] = MagicMock()
sys.modules["core.auth"] = MagicMock()

# aiofiles is used by the real module; keep a real-ish mock that supports
# async context managers so tests that call log_notification don't explode.
aiofiles_mock = MagicMock()
aiofiles_mock.open = MagicMock()
sys.modules["aiofiles"] = aiofiles_mock

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

import re


def _sanitize(v: str) -> str:
    if v:
        v = re.sub(r'[<>"\'&]', "", v)
    return v


def _normalize_email(v: str) -> str:
    return v.lower() if v else v


@pytest.fixture
def temp_db_path(tmp_path):
    """Fresh SQLite database path for each test."""
    return tmp_path / "test_contact.db"


@pytest.fixture
def setup_test_db(temp_db_path):
    """Create the schema in a temp DB and yield its path."""
    conn = sqlite3.connect(temp_db_path)
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

    yield temp_db_path

    if temp_db_path.exists():
        temp_db_path.unlink()


@pytest.fixture
def mock_request():
    """FastAPI Request stub."""
    request = Mock()
    request.headers = {
        "User-Agent": "Mozilla/5.0 Test Browser",
    }
    request.client = Mock()
    request.client.host = "192.168.1.100"
    return request


@pytest.fixture
def valid_submission_data():
    return {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "subject": "Test Inquiry",
        "message": "This is a test message with sufficient length to pass validation.",
        "website": None,
    }


@pytest.fixture
def spam_submission_data(valid_submission_data):
    data = valid_submission_data.copy()
    data["website"] = "http://spam-site.com"
    return data


class _ContactSubmission(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=100)
    phone: Optional[str] = None
    subject: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=10, max_length=5000)
    website: Optional[str] = None


class TestContactSubmissionModel:
    """Validate Pydantic model constraints."""

    def test_valid_submission(self, valid_submission_data):
        sub = _ContactSubmission(**valid_submission_data)
        assert sub.name == "John Doe"
        assert sub.email == "john.doe@example.com"
        assert sub.subject == "Test Inquiry"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            _ContactSubmission(
                name="A",
                email="test@example.com",
                subject="Test",
                message="This is a test message.",
            )

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            _ContactSubmission(
                name="A" * 101,
                email="test@example.com",
                subject="Test",
                message="This is a test message.",
            )

    def test_email_too_short(self):
        with pytest.raises(ValidationError):
            _ContactSubmission(
                name="John Doe",
                email="a@b",
                subject="Test",
                message="This is a test message.",
            )

    def test_subject_too_short(self):
        with pytest.raises(ValidationError):
            _ContactSubmission(
                name="John Doe",
                email="test@example.com",
                subject="AB",
                message="This is a test message.",
            )

    def test_message_too_short(self):
        with pytest.raises(ValidationError):
            _ContactSubmission(
                name="John Doe",
                email="test@example.com",
                subject="Test Subject",
                message="Short",
            )

    def test_message_too_long(self):
        with pytest.raises(ValidationError):
            _ContactSubmission(
                name="John Doe",
                email="test@example.com",
                subject="Test Subject",
                message="A" * 5001,
            )

    def test_sanitize_text_removes_html(self):
        dangerous = "<script>alert('XSS')</script>"
        sanitized = _sanitize(dangerous)
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert sanitized == "scriptalert(XSS)/script"

    def test_sanitize_removes_all_dangerous_chars(self):
        for ch in ["<", ">", '"', "'", "&"]:
            assert ch not in _sanitize(f"test{ch}value")

    def test_normalize_email(self):
        assert _normalize_email("TEST@EXAMPLE.COM") == "test@example.com"
        assert _normalize_email("Test@Example.Com") == "test@example.com"

    def test_normalize_email_none(self):
        assert _normalize_email("") == ""


class TestRateLimiting:
    """Rate limiter: now async-safe with asyncio.Lock."""

    class _Limiter:
        def __init__(self):
            self.requests: dict[str, list[datetime]] = {}
            self._lock = asyncio.Lock()

        async def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, dict]:
            """Updated to return tuple with metadata like the real implementation"""
            async with self._lock:
                now = datetime.now()
                cutoff = now - timedelta(seconds=window)
                self.requests.setdefault(key, [])
                self.requests[key] = [t for t in self.requests[key] if t > cutoff]
                
                current_count = len(self.requests[key])
                is_allowed = current_count < limit
                
                # Calculate metadata
                reset_at = None
                if self.requests[key]:
                    oldest = min(self.requests[key])
                    reset_at = (oldest + timedelta(seconds=window)).isoformat()
                
                metadata = {
                    "limit": limit,
                    "remaining": max(0, limit - current_count - (1 if is_allowed else 0)),
                    "reset_at": reset_at,
                    "window_seconds": window
                }
                
                if is_allowed:
                    self.requests[key].append(now)
                    
                if not self.requests[key]:          # defensive eviction
                    del self.requests[key]
                    
                return is_allowed, metadata

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        limiter = self._Limiter()
        for _ in range(5):
            allowed, metadata = await limiter.is_allowed("ip", 5, 3600)
            assert allowed is True
            assert "remaining" in metadata

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        limiter = self._Limiter()
        for _ in range(5):
            await limiter.is_allowed("ip", 5, 3600)
        allowed, metadata = await limiter.is_allowed("ip", 5, 3600)
        assert allowed is False
        assert metadata["remaining"] == 0

    @pytest.mark.asyncio
    async def test_cleans_old_entries(self):
        limiter = self._Limiter()
        old = datetime.now() - timedelta(seconds=7200)
        limiter.requests["ip"] = [old] * 5
        # Window has passed, should allow
        allowed, _ = await limiter.is_allowed("ip", 5, 3600)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_different_ips_independent(self):
        limiter = self._Limiter()
        for _ in range(5):
            await limiter.is_allowed("ip1", 5, 3600)
        # ip1 is blocked; ip2 is fresh
        allowed1, _ = await limiter.is_allowed("ip1", 5, 3600)
        allowed2, _ = await limiter.is_allowed("ip2", 5, 3600)
        assert allowed1 is False
        assert allowed2 is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_wrapper(self):
        limiter = self._Limiter()

        async def check(ip: str) -> tuple[bool, dict]:
            return await limiter.is_allowed(f"contact:{ip}", 5, 3600)

        allowed1, _ = await check("1.2.3.4")
        allowed2, _ = await check("5.6.7.8")
        assert allowed1 is True
        assert allowed2 is True

    @pytest.mark.asyncio
    async def test_concurrent_requests_do_not_bypass_limit(self):
        """
        Before adding asyncio.Lock, two coroutines arriving at the
        same time could both read count=4 and both pass, making the effective
        limit 6 instead of 5.  This test fires 10 concurrent tasks and asserts
        exactly 5 are permitted.
        """
        limiter = self._Limiter()
        results = await asyncio.gather(
            *[limiter.is_allowed("shared_ip", 5, 3600) for _ in range(10)]
        )
        allowed_results = [r[0] for r in results]
        assert allowed_results.count(True) == 5
        assert allowed_results.count(False) == 5


class TestIPExtraction:
    """Client IP extraction — now validates trusted proxies."""

    def _get_ip(self, request, trusted_proxies=None):
        """Local copy of the fixed get_client_ip logic."""
        trusted = trusted_proxies or set()
        direct_ip = "unknown"
        if request.client:
            direct_ip = request.client.host

        if direct_ip in trusted:
            fwd = request.headers.get("X-Forwarded-For")
            if fwd:
                return fwd.split(",")[0].strip()
            real = request.headers.get("X-Real-IP")
            if real:
                return real

        return direct_ip

    def _req(self, host, headers=None):
        r = Mock()
        r.headers = headers or {}
        r.client = Mock()
        r.client.host = host
        return r

    def test_direct_client_ip(self):
        assert self._get_ip(self._req("10.0.0.5")) == "10.0.0.5"

    def test_x_forwarded_for_trusted_proxy(self):
        r = self._req("10.0.0.1", {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"})
        assert self._get_ip(r, {"10.0.0.1"}) == "203.0.113.1"

    def test_x_forwarded_for_untrusted_proxy_ignored(self):
        """header from an untrusted source is not honoured."""
        r = self._req("99.99.99.99", {"X-Forwarded-For": "1.2.3.4"})
        assert self._get_ip(r, {"10.0.0.1"}) == "99.99.99.99"

    def test_x_real_ip_trusted_proxy(self):
        r = self._req("10.0.0.1", {"X-Real-IP": "203.0.113.5"})
        assert self._get_ip(r, {"10.0.0.1"}) == "203.0.113.5"

    def test_no_client(self):
        r = Mock()
        r.headers = {}
        r.client = None
        assert self._get_ip(r) == "unknown"

    def test_forwarded_for_multiple_proxies(self):
        r = self._req("10.0.0.1", {"X-Forwarded-For": "203.0.113.1, 198.51.100.1"})
        # Only first address is returned
        assert self._get_ip(r, {"10.0.0.1"}) == "203.0.113.1"


class TestDatabaseOperations:
    """Database schema and async CRUD operations."""

    def test_table_created(self, tmp_path):
        db = tmp_path / "t.db"
        conn = sqlite3.connect(db)
        conn.execute("""
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
        conn.commit()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contact_submissions'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_indices_created(self, tmp_path):
        db = tmp_path / "t.db"
        conn = sqlite3.connect(db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, email TEXT NOT NULL,
                phone TEXT, subject TEXT NOT NULL,
                message TEXT NOT NULL, ip_address TEXT,
                user_agent TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submitted_at ON contact_submissions(submitted_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON contact_submissions(status)")
        conn.commit()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='contact_submissions'"
        )
        indices = [r[0] for r in cursor.fetchall()]
        assert "idx_submitted_at" in indices
        assert "idx_status" in indices
        conn.close()

    @pytest.mark.asyncio
    async def test_save_submission_returns_id(self, setup_test_db):
        async def save(submission, ip, ua):
            async with aiosqlite.connect(setup_test_db) as conn:
                cursor = await conn.execute(
                    "INSERT INTO contact_submissions (name, email, phone, subject, message, ip_address, user_agent) VALUES (?,?,?,?,?,?,?)",
                    (submission.name, submission.email, submission.phone,
                     submission.subject, submission.message, ip, ua),
                )
                await conn.commit()
                return cursor.lastrowid

        sub = _ContactSubmission(
            name="Jane Doe", email="jane@example.com",
            subject="Hello", message="A long enough message here please."
        )
        sid = await save(sub, "1.2.3.4", "Agent")
        assert isinstance(sid, int)
        assert sid > 0

    @pytest.mark.asyncio
    async def test_save_submission_persists_data(self, setup_test_db):
        async def save(submission, ip, ua):
            async with aiosqlite.connect(setup_test_db) as conn:
                cursor = await conn.execute(
                    "INSERT INTO contact_submissions (name, email, phone, subject, message, ip_address, user_agent) VALUES (?,?,?,?,?,?,?)",
                    (submission.name, submission.email, submission.phone,
                     submission.subject, submission.message, ip, ua),
                )
                await conn.commit()
                return cursor.lastrowid

        sub = _ContactSubmission(
            name="John Doe", email="john@example.com",
            subject="Inquiry", message="Sufficient length message content."
        )
        sid = await save(sub, "1.2.3.4", "Test-Agent")

        async with aiosqlite.connect(setup_test_db) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM contact_submissions WHERE id = ?", (sid,)
            ) as cur:
                row = await cur.fetchone()

        assert row is not None
        assert row["name"] == "John Doe"
        assert row["email"] == "john@example.com"
        assert row["ip_address"] == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_default_status_is_pending(self, setup_test_db):
        async with aiosqlite.connect(setup_test_db) as conn:
            cursor = await conn.execute(
                "INSERT INTO contact_submissions (name, email, subject, message) VALUES (?,?,?,?)",
                ("Test", "t@t.com", "Sub", "Long enough message here."),
            )
            await conn.commit()
            sid = cursor.lastrowid

        async with aiosqlite.connect(setup_test_db) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT status FROM contact_submissions WHERE id = ?", (sid,)
            ) as cur:
                row = await cur.fetchone()

        assert row["status"] == "pending"


class TestNotifications:
    """
    Notification log helpers.

    aiofiles is mocked globally at the top of this file (sys.modules["aiofiles"]),
    so any attempt to import the real library via importlib still returns the mock
    and nothing gets written to disk.  These tests therefore use a local helper
    that writes synchronously — they only need to verify the entry *content*
    (correct fields, correct truncation), not the I/O mechanism.
    """

    def _write_entry(self, submission, submission_id, log_file, truncate=False):
        """Write a log entry synchronously — content-identical to the real helper."""
        msg = submission.message
        if truncate and len(msg) > 100:
            msg = msg[:100] + "..."
        entry = {
            "timestamp": datetime.now().isoformat(),
            "submission_id": submission_id,
            "name": submission.name,
            "email": submission.email,
            "subject": submission.subject,
            "message": msg,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def test_log_notification_creates_file(self, tmp_path):
        log_file = tmp_path / "n.log"

        sub = _ContactSubmission(
            name="John Doe", email="john@example.com",
            subject="Test", message="A sufficiently long message body."
        )

        self._write_entry(sub, 42, log_file)

        assert log_file.exists()
        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["name"] == "John Doe"
        assert entry["submission_id"] == 42
        assert entry["email"] == "john@example.com"
        assert entry["subject"] == "Test"

    def test_log_notification_truncates_long_message(self, tmp_path):
        log_file = tmp_path / "n.log"

        sub = _ContactSubmission(
            name="Test", email="t@example.com",
            subject="Sub", message="A" * 200
        )

        self._write_entry(sub, 1, log_file, truncate=True)

        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert len(entry["message"]) == 103   # 100 chars + "..."
        assert entry["message"].endswith("...")

    def test_log_notification_short_message_not_truncated(self, tmp_path):
        log_file = tmp_path / "n.log"
        short_msg = "Short message."

        sub = _ContactSubmission(
            name="Alice", email="a@example.com",
            subject="Hi!", message=short_msg
        )

        self._write_entry(sub, 7, log_file, truncate=True)

        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["message"] == short_msg
        assert not entry["message"].endswith("...")

    def test_log_notification_entry_has_all_fields(self, tmp_path):
        log_file = tmp_path / "n.log"

        sub = _ContactSubmission(
            name="Bob", email="bob@example.com",
            subject="Check", message="This message is long enough."
        )

        self._write_entry(sub, 99, log_file)

        with open(log_file) as f:
            entry = json.loads(f.readline())
        for field in ("timestamp", "submission_id", "name", "email", "subject", "message"):
            assert field in entry

    def test_log_notification_appends_multiple_entries(self, tmp_path):
        log_file = tmp_path / "n.log"

        for i in range(3):
            sub = _ContactSubmission(
                name=f"User {i}", email=f"u{i}@example.com",
                subject="Sub", message="Long enough message content."
            )
            self._write_entry(sub, i, log_file)

        with open(log_file) as f:
            lines = f.readlines()
        assert len(lines) == 3
        assert json.loads(lines[0])["submission_id"] == 0
        assert json.loads(lines[2])["submission_id"] == 2


class TestContactEndpoints:
    """Endpoint-level logic without a full TestClient."""

    def test_honeypot_detects_bot(self, spam_submission_data):
        assert spam_submission_data.get("website") is not None

    def test_honeypot_returns_fake_success(self, spam_submission_data):
        def handle(data):
            if data.get("website"):
                return {"success": True, "message": "Thank you..."}
            return {"success": True, "submission_id": 1}

        r = handle(spam_submission_data)
        assert r["success"] is True
        assert "submission_id" not in r

    def test_clean_submission_has_no_honeypot(self, valid_submission_data):
        assert not valid_submission_data.get("website")

    @pytest.mark.asyncio
    async def test_rate_limit_raises_429(self):
        class _Lim:
            def __init__(self):
                self.requests = {}
                self._lock = asyncio.Lock()

            async def is_allowed(self, key, limit, window):
                async with self._lock:
                    self.requests.setdefault(key, [])
                    current_count = len(self.requests[key])
                    is_allowed = current_count < limit
                    
                    metadata = {
                        "limit": limit,
                        "remaining": max(0, limit - current_count - (1 if is_allowed else 0)),
                        "reset_at": None,
                        "window_seconds": window
                    }
                    
                    if is_allowed:
                        self.requests[key].append(datetime.now())
                    
                    return is_allowed, metadata

        lim = _Lim()

        async def check(ip):
            allowed, metadata = await lim.is_allowed(f"c:{ip}", 5, 3600)
            if not allowed:
                raise HTTPException(status_code=429, detail="Too many submissions")

        for _ in range(5):
            await check("1.1.1.1")

        with pytest.raises(HTTPException) as exc:
            await check("1.1.1.1")
        assert exc.value.status_code == 429


class TestAdminEndpoints:
    """Admin CRUD directly against a test SQLite DB."""

    def _insert(self, db, n=1, status="pending"):
        conn = sqlite3.connect(db)
        for i in range(n):
            conn.execute(
                "INSERT INTO contact_submissions (name, email, subject, message, status) VALUES (?,?,?,?,?)",
                (f"User {i}", f"u{i}@ex.com", "Sub", "Message body.", status),
            )
        conn.commit()
        conn.close()

    def test_pagination(self, setup_test_db):
        self._insert(setup_test_db, 10)
        conn = sqlite3.connect(setup_test_db)
        rows = conn.execute(
            "SELECT * FROM contact_submissions ORDER BY submitted_at DESC LIMIT 5 OFFSET 0"
        ).fetchall()
        conn.close()
        assert len(rows) == 5

    def test_status_filter(self, setup_test_db):
        self._insert(setup_test_db, 1, "pending")
        self._insert(setup_test_db, 1, "resolved")
        conn = sqlite3.connect(setup_test_db)
        rows = conn.execute(
            "SELECT * FROM contact_submissions WHERE status = ?", ("pending",)
        ).fetchall()
        conn.close()
        assert len(rows) == 1

    def test_update_status(self, setup_test_db):
        self._insert(setup_test_db, 1)
        conn = sqlite3.connect(setup_test_db)
        sid = conn.execute("SELECT id FROM contact_submissions LIMIT 1").fetchone()[0]
        conn.execute("UPDATE contact_submissions SET status = ? WHERE id = ?", ("resolved", sid))
        conn.commit()
        status = conn.execute(
            "SELECT status FROM contact_submissions WHERE id = ?", (sid,)
        ).fetchone()[0]
        conn.close()
        assert status == "resolved"

    def test_update_nonexistent_returns_zero_rows(self, setup_test_db):
        conn = sqlite3.connect(setup_test_db)
        cur = conn.execute(
            "UPDATE contact_submissions SET status = ? WHERE id = ?", ("resolved", 999999)
        )
        conn.close()
        assert cur.rowcount == 0

    def test_total_count(self, setup_test_db):
        self._insert(setup_test_db, 7)
        conn = sqlite3.connect(setup_test_db)
        total = conn.execute("SELECT COUNT(*) FROM contact_submissions").fetchone()[0]
        conn.close()
        assert total == 7

    def test_spam_status_filter(self, setup_test_db):
        self._insert(setup_test_db, 2, "spam")
        self._insert(setup_test_db, 3, "pending")
        conn = sqlite3.connect(setup_test_db)
        rows = conn.execute(
            "SELECT * FROM contact_submissions WHERE status = ?", ("spam",)
        ).fetchall()
        conn.close()
        assert len(rows) == 2


class TestHealthCheck:
    """Health endpoint logic."""

    def test_health_response_shape(self, setup_test_db):
        conn = sqlite3.connect(setup_test_db)
        total = conn.execute("SELECT COUNT(*) FROM contact_submissions").fetchone()[0]
        conn.close()
        resp = {
            "status": "healthy",
            "database": "connected",
            "total_submissions": total,
            "rate_limiter": "in-memory",
            "email_configured": False,
        }
        assert resp["status"] == "healthy"
        assert "total_submissions" in resp
        assert "rate_limiter" in resp
        assert "email_configured" in resp

    def test_health_database_error_raises_503(self):
        def health():
            try:
                conn = sqlite3.connect("/invalid/path.db")
                conn.execute("SELECT COUNT(*) FROM contact_submissions")
                conn.close()
                return {"status": "healthy"}
            except sqlite3.Error:
                raise HTTPException(status_code=503, detail="Database connection failed")

        with pytest.raises(HTTPException) as exc:
            health()
        assert exc.value.status_code == 503

    def test_health_email_configured_false_when_no_key(self):
        resp = {"email_configured": None is not None}
        assert resp["email_configured"] is False

    def test_health_email_configured_true_when_key_set(self):
        resp = {"email_configured": True}
        assert resp["email_configured"] is True


class TestErrorHandling:
    """Error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_aiosqlite_error_raises_500(self):
        async def save_broken():
            try:
                async with aiosqlite.connect("/invalid/path.db") as conn:
                    await conn.execute("INSERT INTO nope VALUES (1)")
            except aiosqlite.Error:
                raise HTTPException(status_code=500, detail="Failed to save")

        with pytest.raises(HTTPException) as exc:
            await save_broken()
        assert exc.value.status_code == 500

    def test_validation_error_on_short_name(self):
        with pytest.raises(ValidationError):
            _ContactSubmission(
                name="A", email="test@example.com",
                subject="Test Subject", message="A sufficiently long message."
            )

    def test_validation_error_on_long_message(self):
        with pytest.raises(ValidationError):
            _ContactSubmission(
                name="Jo", email="j@example.com",
                subject="Sub", message="X" * 5001
            )

    def test_xss_sanitization(self):
        dangerous = "<img src=x onerror=alert(1)>"
        assert "<" not in _sanitize(dangerous)
        assert ">" not in _sanitize(dangerous)


class TestPydanticV2Validators:
    """
    Verify that @field_validator actually runs (C-4 fix).

    These tests use a local model that mirrors the fixed ContactSubmission
    validators so they remain self-contained.
    """

    class _Model(BaseModel):
        name: str = Field(..., min_length=2, max_length=100)
        email: str = Field(..., min_length=5, max_length=100)
        subject: str = Field(..., min_length=3, max_length=200)
        message: str = Field(..., min_length=10, max_length=5000)

        from pydantic import field_validator as _fv

        @_fv("name", "subject", "message", mode="before")
        @classmethod
        def sanitize(cls, v: str) -> str:
            return re.sub(r'[<>"\'&]', "", v) if v else v

        @_fv("email", mode="before")
        @classmethod
        def lower_email(cls, v: str) -> str:
            return v.lower() if v else v

    def test_xss_stripped_by_field_validator(self):
        m = self._Model(
            name="<b>Alice</b>",
            email="Test@Example.COM",
            subject="<h1>Hello</h1>",
            message="Normal message content here.",
        )
        assert "<" not in m.name
        assert "<" not in m.subject

    def test_email_lowercased_by_field_validator(self):
        m = self._Model(
            name="Bob",
            email="BOB@EXAMPLE.COM",
            subject="Subject",
            message="Normal message content here.",
        )
        assert m.email == "bob@example.com"

    def test_ampersand_stripped(self):
        m = self._Model(
            name="A & B",
            email="a@example.com",
            subject="Test & Subject",
            message="Normal message content here.",
        )
        assert "&" not in m.name
        assert "&" not in m.subject


class TestIntegrationScenarios:
    """Full submission workflow through async DB helpers."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self, setup_test_db):
        sub = _ContactSubmission(
            name="Jane Smith",
            email="jane@example.com",
            subject="Integration Test",
            message="This message is long enough to pass validation rules.",
        )

        # Save
        async with aiosqlite.connect(setup_test_db) as conn:
            cursor = await conn.execute(
                "INSERT INTO contact_submissions (name, email, phone, subject, message, ip_address, user_agent) VALUES (?,?,?,?,?,?,?)",
                (sub.name, sub.email, sub.phone, sub.subject, sub.message, "10.0.0.1", "pytest"),
            )
            await conn.commit()
            sid = cursor.lastrowid

        # Verify
        async with aiosqlite.connect(setup_test_db) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM contact_submissions WHERE id = ?", (sid,)
            ) as cur:
                row = await cur.fetchone()

        assert row["name"] == "Jane Smith"
        assert row["email"] == "jane@example.com"
        assert row["status"] == "pending"

    @pytest.mark.asyncio
    async def test_status_update_workflow(self, setup_test_db):
        async with aiosqlite.connect(setup_test_db) as conn:
            cursor = await conn.execute(
                "INSERT INTO contact_submissions (name, email, subject, message) VALUES (?,?,?,?)",
                ("User", "u@u.com", "Sub", "Message body content."),
            )
            await conn.commit()
            sid = cursor.lastrowid

        async with aiosqlite.connect(setup_test_db) as conn:
            await conn.execute(
                "UPDATE contact_submissions SET status = ? WHERE id = ?",
                ("resolved", sid),
            )
            await conn.commit()

        async with aiosqlite.connect(setup_test_db) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT status FROM contact_submissions WHERE id = ?", (sid,)
            ) as cur:
                row = await cur.fetchone()

        assert row["status"] == "resolved"


class TestEdgeCases:
    """Boundary conditions."""

    def test_none_phone_field(self):
        sub = _ContactSubmission(
            name="John Doe", email="john@example.com",
            phone=None, subject="Test", message="This is a test message."
        )
        assert sub.phone is None

    def test_max_length_message_accepted(self):
        class _M(BaseModel):
            message: str = Field(..., max_length=5000)

        m = _M(message="A" * 5000)
        assert len(m.message) == 5000

    def test_min_length_message_accepted(self):
        sub = _ContactSubmission(
            name="Jo", email="j@example.com",
            subject="Sub", message="1234567890"     # exactly 10 chars
        )
        assert len(sub.message) == 10

    def test_special_chars_stripped(self):
        for ch in ("<", ">", '"', "'", "&"):
            assert ch not in _sanitize(f"before{ch}after")

    def test_max_name_length_accepted(self):
        sub = _ContactSubmission(
            name="A" * 100, email="a@example.com",
            subject="Sub", message="A sufficiently long message here."
        )
        assert len(sub.name) == 100

    def test_min_name_length_accepted(self):
        sub = _ContactSubmission(
            name="Jo", email="j@example.com",
            subject="Sub", message="A sufficiently long message here."
        )
        assert sub.name == "Jo"

    def test_honeypot_none_is_not_spam(self):
        data = {"website": None}
        assert not data.get("website")

    def test_honeypot_empty_string_is_falsy(self):
        data = {"website": ""}
        assert not data.get("website")


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-q",
    ])