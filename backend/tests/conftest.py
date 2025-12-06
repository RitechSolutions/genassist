import sys
from pathlib import Path
import pytest
from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config.settings import settings
from app.db.seed.seed_data_config import seed_test_data


@pytest.fixture(scope="session")
def anyio_backend():
    return 'asyncio'

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app

@pytest.fixture(scope="session")
def app_def():
    return create_app()

@pytest.fixture(scope="session")
def client(app_def):
    with TestClient(app_def) as client:
        yield client


@pytest.fixture(scope="session")
def token(client, request):
    role = getattr(request, "param", "admin")  # default role

    if role == "admin":
        credentials = {
            "username": seed_test_data.admin_username,
            "password": seed_test_data.admin_password
            }
    else:
        credentials = {
            "username": seed_test_data.supervisor_username,
            "password": seed_test_data.supervisor_password
            }

    # Use form data instead of JSON
    response = client.post("/api/auth/token", data=credentials)
    assert response.status_code == 200, f"Login failed: {response.text}"

    data = response.json()
    return data["access_token"]


@pytest.fixture(scope="session")
def authorized_client(client, token):
    """
    Returns the same TestClient but with Authorization headers set.
    All requests made with this client will include the token.
    """
    # 1. Strip the Bearer token (if one was previously added)
    client.headers.pop("X-Api-Key", None)  # ignore KeyError if it wasn't there
    client.headers.update({"Authorization": f"Bearer {token}"})

    return client

@pytest.fixture(scope="session")
def authorized_client_agent(client, token):
    """
    Returns the same TestClient but with Authorization headers set.
    All requests made with this client will include the token.
    """
    # 1. Strip the Bearer token (if one was previously added)
    client.headers.pop("Authorization", None)  # ignore KeyError if it wasn't there

    # 2. Add the API‑key header
    client.headers.update({"X-API-Key": "agent123"})

    return client


# Create an asynchronous engine
engine = create_async_engine(settings.DATABASE_URL)

# Create a session factory
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope="session")
async def async_engine():
    try:
        yield engine
    finally:
        print("Disposing engine")
        #await engine.dispose()


@pytest.fixture(scope="session")
async def async_db_session(async_engine):
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            print("Closing session")