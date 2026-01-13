"""
Simple Contact API Test - Manual verification script

This script tests the basic functionality of the contact API without requiring
a full test setup. It's meant for quick verification during development.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that we can import the contact module"""
    print("✓ Testing imports...")
    try:
        from api import contact
        print("  ✓ Successfully imported api.contact")
        return True
    except Exception as e:
        print(f"  ✗ Failed to import: {e}")
        return False

def test_models():
    """Test Pydantic models"""
    print("\n✓ Testing Pydantic models...")
    try:
        from api.contact import ContactSubmission
        
        # Valid submission
        valid_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "subject": "Test Subject",
            "message": "This is a test message with enough characters."
        }
        submission = ContactSubmission(**valid_data)
        print(f"  ✓ Valid submission created: {submission.name}")
        
        # Test email normalization
        submission2 = ContactSubmission(**{
            **valid_data,
            "email": "JOHN@EXAMPLE.COM"
        })
        assert submission2.email == "john@example.com", "Email should be normalized to lowercase"
        print("  ✓ Email normalization works")
        
        # Test XSS sanitization
        submission3 = ContactSubmission(**{
            "name": "Test<script>alert('xss')</script>",
            "email": "test@example.com",
            "subject": "Subject",
            "message": "Message with <b>HTML</b> tags"
        })
        assert "<script>" not in submission3.name, "Script tags should be removed"
        assert "<b>" not in submission3.message, "HTML tags should be removed"
        print("  ✓ XSS sanitization works")
        
        return True
    except Exception as e:
        print(f"  ✗ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database():
    """Test database initialization"""
    print("\n✓ Testing database initialization...")
    try:
        from api.contact import init_database, DB_PATH
        import sqlite3
        
        # Initialize database
        init_database()
        print(f"  ✓ Database initialized at: {DB_PATH}")
        
        # Check table exists
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contact_submissions'")
        table_exists = cursor.fetchone() is not None
        conn.close()
        
        if table_exists:
            print("  ✓ contact_submissions table exists")
            return True
        else:
            print("  ✗ contact_submissions table not found")
            return False
            
    except Exception as e:
        print(f"  ✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rate_limiter():
    """Test rate limiting functionality"""
    print("\n✓ Testing rate limiter...")
    try:
        from api.contact import check_rate_limit
        
        # Test rate limiting
        test_ip = "192.168.1.100"
        
        # Should allow first requests
        for i in range(5):
            allowed = check_rate_limit(test_ip)
            if not allowed:
                print(f"  ✗ Should have allowed request {i+1}")
                return False
        
        print("  ✓ Rate limiter allows 5 requests")
        
        # 6th request should be rate limited
        allowed = check_rate_limit(test_ip)
        if allowed:
            print("  ✗ Rate limiter should have blocked 6th request")
            return False
        
        print("  ✓ Rate limiter blocks 6th request")
        return True
        
    except Exception as e:
        print(f"  ✗ Rate limiter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_validation():
    """Test field validation"""
    print("\n✓ Testing field validation...")
    try:
        from api.contact import ContactSubmission
        from pydantic import ValidationError
        
        # Test missing required field
        try:
            ContactSubmission(
                name="John",
                email="john@example.com",
                subject="Test"
                # Missing message
            )
            print("  ✗ Should have raised validation error for missing message")
            return False
        except ValidationError:
            print("  ✓ Correctly rejects missing required fields")
        
        # Test invalid email
        try:
            ContactSubmission(
                name="John",
                email="not-an-email",
                subject="Test",
                message="Test message content"
            )
            print("  ✗ Should have raised validation error for invalid email")
            return False
        except ValidationError:
            print("  ✓ Correctly rejects invalid email")
        
        # Test message too short
        try:
            ContactSubmission(
                name="John",
                email="john@example.com",
                subject="Test",
                message="Short"
            )
            print("  ✗ Should have raised validation error for short message")
            return False
        except ValidationError:
            print("  ✓ Correctly rejects short messages")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Validation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("Contact API Test Suite")
    print("=" * 70)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Models", test_models()))
    results.append(("Database", test_database()))
    results.append(("Rate Limiter", test_rate_limiter()))
    results.append(("Validation", test_validation()))
    
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{name:20s} {status}")
    
    print("=" * 70)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 70)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
