import os

# Must be set before the app is imported. CI overrides DATABASE_URL with real Postgres.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123")
os.environ.setdefault("SEED_PASSWORD", "test-password-1")
os.environ.setdefault("PBKDF2_ITERATIONS", "1000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app, init_db  # noqa: E402

PASSWORD = os.environ["SEED_PASSWORD"]


@pytest.fixture()
def client():
    """Fresh, seeded database for every test."""
    models.Base.metadata.drop_all(engine)
    init_db()
    app.dependency_overrides.clear()
    return TestClient(app)


def login(client: TestClient, username: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def teacher_a(client):
    return login(client, "teacher_a")


@pytest.fixture()
def teacher_b(client):
    return login(client, "teacher_b")


@pytest.fixture()
def admin(client):
    return login(client, "admin1")


@pytest.fixture()
def student(client):
    return login(client, "student1")
