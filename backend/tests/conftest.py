import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./.test_aiops.db"
os.environ["JWT_SECRET"] = "test-secret-with-more-than-thirty-two-characters"
os.environ["DEMO_SEED_ENABLED"] = "true"
os.environ.pop("OPENAI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import demo_password, seed_demo_data


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_demo_data(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def operator_headers(client):
    response = client.post("/auth/token", data={"username": "operator", "password": demo_password("operator")})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def manager_headers(client):
    response = client.post("/auth/token", data={"username": "manager", "password": demo_password("manager")})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
