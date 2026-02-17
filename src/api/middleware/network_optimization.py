"""
Network Optimization Middleware for FastAPI
Handles content compression (Zstd) and other network optimizations.
"""

from starlette.types import ASGIApp, Receive, Scope, Send, Message
import zstandard as zstd
import logging

logger = logging.getLogger(__name__)

class ZstdMiddleware:
    """
    Middleware to handle Zstd compressed requests.
    Decompresses the body if Content-Encoding is 'zstd'.

    Rewritten as pure ASGI middleware to avoid BaseHTTPMiddleware conflicts.
    """
    def __init__(self, app: ASGIApp):
        self.app = app
        self.decompressor = zstd.ZstdDecompressor()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check headers for content-encoding: zstd
        headers = scope.get("headers", [])
        is_zstd = False
        for k, v in headers:
            if k.lower() == b"content-encoding" and v.lower() == b"zstd":
                is_zstd = True
                break

        if is_zstd:
            try:
                # Read the entire body
                body = b""
                more_body = True
                while more_body:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        # Client disconnected during upload
                        return
                    if message["type"] == "http.request":
                        body += message.get("body", b"")
                        more_body = message.get("more_body", False)

                # Decompress
                decompressed = self.decompressor.decompress(body)

                # Create a wrapped receive function
                # We deliver the full decompressed body in one go
                consumed = False

                async def wrapped_receive() -> Message:
                    nonlocal consumed
                    if not consumed:
                        consumed = True
                        return {"type": "http.request", "body": decompressed, "more_body": False}
                    # If called again, mimic end of stream or disconnect
                    return {"type": "http.disconnect"}

                await self.app(scope, wrapped_receive, send)
                return

            except Exception as e:
                logger.error(f"Zstd decompression failed: {e}")
                # Return 400 Bad Request
                await send({
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [(b"content-type", b"text/plain")]
                })
                await send({
                    "type": "http.response.body",
                    "body": b"Decompression failed"
                })
                return

        # Pass through for non-zstd requests
        await self.app(scope, receive, send)
