import pytest
from fastapi.testclient import TestClient
from main import app, get_db
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import uuid
import datetime  

DATABASE_URL = "postgresql://postgres:4450@localhost/test"
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def clear_test_database():
    # Clear the database before each test
    with engine.connect() as connection:
        trans = connection.begin()
        connection.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        trans.commit()


client = TestClient(app)


# Retrieve an access token for authentication
@pytest.fixture
def get_access_token():
    def _get_access_token(username, password):
        response = client.post("/token", data={"username": username, "password": password})
        
        return response.json()["access_token"]

    return _get_access_token


# Test user registration
def generate_username():
    return f"testuser_{uuid.uuid4().hex[:8]}"


def test_register_user():
    username = generate_username()
    response = client.post("/register", json={"username": username, "password": "testpassword"})
    assert response.status_code == 200
    assert response.json() == {"message": "User registered successfully"}


@pytest.mark.usefixtures("clear_test_database")
def test_login(get_access_token):
    username = generate_username()
    client.post("/register", json={"username": username, "password": "testpassword"})
    access_token = get_access_token(username, "testpassword")
    response = client.post("/token", data={"username": username, "password": "testpassword"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def generate_filename(file_extension="txt"):
    return f"testfile_{uuid.uuid4().hex[:8]}.{file_extension}"


@pytest.mark.usefixtures("clear_test_database")
def test_upload_file(get_access_token):
    username = generate_username()
    # Register the user before trying to log in
    client.post("/register", json={"username": username, "password": "testpassword"})
    
    files = {
        "file": ("testfile.txt", b"file content"),
        "expiry_date": (None, datetime.datetime(2024, 2, 2).isoformat()),
    }
    access_token = get_access_token(username, "testpassword")

    response = client.post("/upload-file/", files=files, headers={"Authorization": f"Bearer {access_token}"})

    

    assert response.status_code == 200
    assert "file_code" in response.json() and "expiry_date" in response.json()

def finalizer():
    if get_db in app.dependency_overrides:
        app.dependency_overrides.pop(get_db)
    engine.dispose()


# Use pytest fixture to run the finalizer after all tests
@pytest.fixture(autouse=True)
def run_after_tests():
    yield
    finalizer()
