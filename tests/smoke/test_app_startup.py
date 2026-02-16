import pytest
from fastapi import FastAPI
from api.service import app

@pytest.mark.smoke
def test_app_starts():
    """Verify that the FastAPI application instance is created successfully."""
    assert app is not None
    assert isinstance(app, FastAPI)
