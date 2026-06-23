import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app, get_db
from app.core.database import Base
from app.core.security import get_password_hash

# Setup separate in-memory testing database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_signup(client):
    response = client.post(
        "/v1/auth/signup",
        data={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["username"] == "testuser"

def test_signup_duplicate(client):
    response = client.post(
        "/v1/auth/signup",
        data={"username": "testuser", "password": "anotherpassword"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already registered"

def test_login(client):
    response = client.post(
        "/v1/auth/login",
        data={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

def test_login_invalid(client):
    response = client.post(
        "/v1/auth/login",
        data={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

def test_get_me(client):
    # Log in to get token
    login_response = client.post(
        "/v1/auth/login",
        data={"username": "testuser", "password": "testpassword"}
    )
    token = login_response.json()["access_token"]
    
    # Access protected route
    response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
