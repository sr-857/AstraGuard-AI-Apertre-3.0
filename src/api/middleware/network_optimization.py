"""
Network Optimization Middleware for FastAPI
Handles content compression (Zstd) and other network optimizations.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send, Message
import zstandard as zstd
import logging

logger = logging.getLogger(__name__)

class ZstdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle Zstd compressed requests.
    Decompresses the body if Content-Encoding is 'zstd'.
    """
    def __init__(self, app):
        super().__init__(app)
        self.decompressor = zstd.ZstdDecompressor()

    async def dispatch(self, request: Request, call_next):
        encoding = request.headers.get("content-encoding", "").lower()

        if encoding == "zstd":
            try:
                # Read the compressed body
                body = await request.body()

                # Decompress
                decompressed = self.decompressor.decompress(body)

                # Replace the body in the request
                # We need to override receive() to return the decompressed bytes
                # as a single http.request message
                async def receive() -> Message:
                    return {"type": "http.request", "body": decompressed, "more_body": False}

                request._receive = receive

                # Update Content-Length header (optional but good practice)
                # But headers are immutable in request.scope usually,
                # or complicated to update.
                # FastAPI doesn't usually strictly enforce Content-Length check vs body read.

            except Exception as e:
                logger.error(f"Zstd decompression failed: {e}")
                return Response("Decompression failed", status_code=400)

        response = await call_next(request)
        return response
