"""Shared pytest fixtures."""

from __future__ import annotations

import os
import pathlib
import shutil

# Force test env BEFORE any app imports read settings.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"
os.environ["LOG_TO_STDOUT"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import create_all, drop_all, init_engine
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def _prepare_dirs():
    settings = get_settings()
    settings.ensure_dirs()
    yield
    # Clean the test DB file so re-runs start fresh.
    db_path = pathlib.Path("./data/test.db")
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


@pytest.fixture(autouse=True)
def _reset_db():
    """Each test gets a clean DB."""
    init_engine()
    drop_all()
    create_all()
    yield


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Register a user and return an Authorization header + refresh + user info."""
    body = {
        "email": "alice@example.com",
        "password": "hunter22-strongpass",
        "display_name": "Alice",
    }
    r = client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    headers = {"Authorization": f"Bearer {data['access']}"}
    return {
        "headers": headers,
        "refresh": data["refresh"],
        "user": data["user"],
        "access": data["access"],
    }
