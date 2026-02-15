#!/usr/bin/env python3
"""Verify that fixes have been applied correctly."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def check_auth_syntax():
    """Check auth.py for syntax errors."""
    auth_file = Path('src/api/auth.py')
    with open(auth_file) as f:
        content = f.read()
    
    # Try to compile it
    try:
        compile(content, str(auth_file), 'exec')
        print(f"✓ auth.py: Syntax OK")
        return True
    except SyntaxError as e:
        print(f"✗ auth.py: SyntaxError at line {e.lineno}: {e.msg}")
        print(f"  {auth_file}:{e.lineno}: {e.text}")
        return False

def check_contact_syntax():
    """Check contact.py for syntax errors."""
    contact_file = Path('src/api/contact.py')
    with open(contact_file) as f:
        content = f.read()
    
    # Try to compile it
    try:
        compile(content, str(contact_file), 'exec')
        print(f"✓ contact.py: Syntax OK")
        return True
    except SyntaxError as e:
        print(f"✗ contact.py: SyntaxError at line {e.lineno}: {e.msg}")
        print(f"  {contact_file}:{e.lineno}: {e.text}")
        return False

def check_imports():
    """Check if modules can be imported."""
    try:
        from api.auth import get_api_key
        print(f"✓ api.auth: Import OK")
    except Exception as e:
        print(f"✗ api.auth: Import Error: {type(e).__name__}: {e}")
        return False
    
    try:
        from api.contact import log_notification
        print(f"✓ api.contact: Import OK")
    except Exception as e:
        print(f"✗ api.contact: Import Error: {type(e).__name__}: {e}")
        return False
    
    return True

if __name__ == '__main__':
    print("Verifying fixes...\n")
    
    results = []
    results.append(("auth.py syntax", check_auth_syntax()))
    results.append(("contact.py syntax", check_contact_syntax()))
    results.append(("imports", check_imports()))
    
    print(f"\n{'='*50}")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("✓ All fixes verified successfully!")
        sys.exit(0)
    else:
        print("✗ Some checks failed")
        sys.exit(1)
