#!/usr/bin/env python3
"""
Quick Start - Contact Form Demo

This script starts the API server and opens the contact page in your browser.
"""

import subprocess
import webbrowser
import time
import sys
from pathlib import Path

def main():
    print("=" * 70)
    print("AstraGuard Contact Form - Quick Start")
    print("=" * 70)
    print()
    
    # Check if we're in the right directory
    if not Path("api/contact.py").exists():
        print("❌ Error: Please run this script from the AstraGuard-AI root directory")
        return 1
    
    print("✓ Starting API server...")
    print()
    print("The server will start on http://localhost:8000")
    print()
    print("Available endpoints:")
    print("  - Main site: http://localhost:8000/docs/index.html")
    print("  - API docs:  http://localhost:8000/docs")
    print("  - Admin:     http://localhost:8000/docs/admin_contact.html")
    print()
    print("To test the contact form:")
    print("  1. Navigate to the main site")
    print("  2. Click 'Contact' in the navigation")
    print("  3. Fill out and submit the form")
    print("  4. Check admin dashboard for submissions")
    print()
    print("=" * 70)
    print()
    
    try:
        # Start the API server
        print("Starting uvicorn server...")
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "api.service:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000"
        ])
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped")
        return 0
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("\nMake sure uvicorn is installed:")
        print("  pip install uvicorn[standard]")
        return 1

if __name__ == "__main__":
    sys.exit(main())
