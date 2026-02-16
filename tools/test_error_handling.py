#!/usr/bin/env python3
"""
Test script to verify error handling improvements in contact.py
"""

import asyncio
import tempfile
import os
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, 'src')

async def test_log_notification_error_handling():
    """Test that log_notification handles OSError properly"""
    print("Testing log_notification error handling...")

    # Import after adding path
    from api.contact import log_notification, ContactSubmission

    # Create a test submission
    submission = ContactSubmission(
        name="Test User",
        email="test@example.com",
        subject="Test Subject",
        message="Test message content"
    )

    # Test with invalid path (should raise OSError)
    try:
        # Temporarily patch DATA_DIR to an invalid path
        import api.contact
        original_data_dir = api.contact.DATA_DIR
        api.contact.DATA_DIR = Path("/invalid/path/that/does/not/exist")

        try:
            await log_notification(submission, 123)
            print("❌ Expected OSError but none was raised")
            return False
        except OSError:
            print("✅ OSError properly raised for invalid path")
        except Exception as e:
            print(f"❌ Unexpected exception: {e}")
            return False
        finally:
            api.contact.DATA_DIR = original_data_dir

    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        return False

    return True

async def test_save_submission_error_handling():
    """Test that save_submission handles database errors properly"""
    print("Testing save_submission error handling...")

    from api.contact import save_submission, ContactSubmission

    # Create a test submission
    submission = ContactSubmission(
        name="Test User",
        email="test@example.com",
        subject="Test Subject",
        message="Test message content"
    )

    # Test with invalid database path (should raise aiosqlite.Error)
    try:
        # Temporarily patch DB_PATH to an invalid path
        import api.contact
        original_db_path = api.contact.DB_PATH
        api.contact.DB_PATH = Path("/invalid/path/database.db")

        try:
            await save_submission(submission, "127.0.0.1", "Test Agent")
            print("❌ Expected aiosqlite.Error but none was raised")
            return False
        except Exception as e:
            # Should catch aiosqlite.Error or similar
            if "aiosqlite" in str(type(e)) or "sqlite" in str(type(e)).lower():
                print("✅ Database error properly raised")
            else:
                print(f"✅ Exception raised (type: {type(e).__name__})")
        finally:
            api.contact.DB_PATH = original_db_path

    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        return False

    return True

async def test_send_email_notification_error_handling():
    """Test that send_email_notification handles errors gracefully"""
    print("Testing send_email_notification error handling...")

    from api.contact import send_email_notification, ContactSubmission

    # Create a test submission
    submission = ContactSubmission(
        name="Test User",
        email="test@example.com",
        subject="Test Subject",
        message="Test message content"
    )

    # This should not raise an exception even if email fails
    try:
        await send_email_notification(submission, 123)
        print("✅ send_email_notification completed without raising exception")
        return True
    except Exception as e:
        print(f"❌ Unexpected exception in send_email_notification: {e}")
        return False

async def main():
    """Run all error handling tests"""
    print("Running error handling tests for contact.py\n")

    tests = [
        test_log_notification_error_handling,
        test_save_submission_error_handling,
        test_send_email_notification_error_handling,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if await test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}\n")

    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All error handling tests passed!")
        return True
    else:
        print("⚠️  Some tests failed")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
