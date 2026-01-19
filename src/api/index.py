"""
AstraGuard AI - Vercel Serverless Function Entry Point
Adapts the FastAPI app for Vercel's serverless environment
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.service import app

# Vercel expects a callable named 'handler' or uses ASGI with app
# This exports the FastAPI app directly for Vercel
__all__ = ["app"]
