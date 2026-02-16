"""
Lightweight FastAPI app exposing only the contact router.
This avoids importing the full `api.service` and its heavy dependencies
so the contact endpoints can be run independently during development.
"""
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from typing import List

from src.api.contact import router as contact_router

logger = logging.getLogger(__name__)



logger: logging.Logger = logging.getLogger(__name__)
app: FastAPI = FastAPI(title="AstraGuard Contact API (dev)")


# Allow local frontend (python http.server) and localhost same-origin
ALLOWED_ORIGINS: List[str] = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Custom handler for validation errors to provide clear, user-friendly messages.
    """
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        msg = error["msg"]
        error_type = error["type"]
        
        # Create user-friendly error messages
        if "min_length" in error_type:
            ctx = error.get("ctx", {})
            min_len = ctx.get("min_length", "required")
            errors.append(f"{field}: Must be at least {min_len} characters long")
        elif "max_length" in error_type:
            ctx = error.get("ctx", {})
            max_len = ctx.get("max_length", "allowed")
            errors.append(f"{field}: Must not exceed {max_len} characters")
        elif "value_error.email" in error_type or "email" in error_type.lower():
            errors.append(f"{field}: Invalid email format")
        elif "missing" in error_type:
            errors.append(f"{field}: This field is required")
        else:
            errors.append(f"{field}: {msg}")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": "Validation failed",
            "message": "Please check your input and try again",
            "details": errors
        }
    )


try:
    app.include_router(contact_router)
except RuntimeError:
    logger.critical(
        "Failed to include contact router in FastAPI application.",
        exc_info=True,
    )
    raise


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    from src.api.contact import init_database
    init_database()
    logger.info("Contact API database initialized")
