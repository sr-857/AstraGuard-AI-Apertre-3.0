"""
Lightweight FastAPI app exposing only the contact router.
This avoids importing the full `api.service` and its heavy dependencies
so the contact endpoints can be run independently during development.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.contact import router as contact_router

app = FastAPI(title="AstraGuard Contact API (dev)")

# Allow local frontend (python http.server) and localhost same-origin
ALLOWED_ORIGINS = [
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

app.include_router(contact_router)
