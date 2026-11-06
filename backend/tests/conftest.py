import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("ANTHROPIC_API_KEY", None)  # tests must run offline, rules-only
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import SessionLocal, init_db
from app.models.db import Base, engine

SAMPLES = Path(__file__).resolve().parents[2] / "sample_data"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def loaded(client):
    for name in ("history_week.csv", "daily_report_morning.xlsx", "evening_notes.txt", "night_report.pdf"):
        r = client.post("/api/upload", files={"file": (name, (SAMPLES / name).read_bytes())})
        assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def db():
    init_db()
    s = SessionLocal()
    yield s
    s.close()
