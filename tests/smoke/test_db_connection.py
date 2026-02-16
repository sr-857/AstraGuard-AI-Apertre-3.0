import pytest
import os
from db.database import get_connection

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_db_connection():
    """Verify database connectivity with a simple query."""
    # Ensure data directory exists for SQLite fallback
    os.makedirs("data", exist_ok=True)

    async with get_connection() as conn:
        async with conn.execute("SELECT 1") as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 1
