"""Core API test fixtures with isolated in-memory DB."""

import os

import pytest

# Must be set before core_api.db is imported.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from core_api.db import Base, SessionLocal, engine  # noqa: E402
from core_api.startup import register_tools  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_db():
    """Reset DB tables per test to avoid persistent state pollution."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        register_tools(db)
    finally:
        db.close()

    yield
