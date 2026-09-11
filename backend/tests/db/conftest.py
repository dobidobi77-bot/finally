"""Every DB test runs against a fresh temporary database."""

import pytest

from app.db.init import close_db, init_db


@pytest.fixture(autouse=True)
async def db_path(tmp_path):
    """Initialise a temp database, and close the connection after the test."""
    path = tmp_path / "finally.db"
    await init_db(str(path))
    yield str(path)
    await close_db()
