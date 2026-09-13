import os
import tempfile
import base64

os.environ["NCDC_ADMIN_USER"] = "admin"
os.environ["NCDC_ADMIN_PASS"] = "test-admin-pass-123"
os.environ["SECRET_KEY"] = "test-secret-key-16chars"
os.environ["PROVISION_AUTH_ENABLED"] = "true"
os.environ["PROVISION_USER"] = "provision"
os.environ["PROVISION_PASS"] = "test-prov-pass"
os.environ["ACTION_URI_TOKEN"] = "test-token-123"
os.environ["AUTO_ENROLL"] = "true"
os.environ["DEBUG"] = "false"
os.environ["PUBLIC_BASE_URL"] = "https://ncdc.test"

_tmp = tempfile.NamedTemporaryFile(prefix="ncdc-test-", suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

ADMIN_AUTH = {
    "Authorization": "Basic "
    + base64.b64encode(b"admin:test-admin-pass-123").decode()
}


@pytest.fixture(scope="session")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_headers(client):
    response = client.get("/", headers=ADMIN_AUTH)
    assert response.status_code == 200
    token = response.cookies.get("ncdc_csrf") or client.cookies.get("ncdc_csrf")
    headers = dict(ADMIN_AUTH)
    if token:
        headers["X-CSRF-Token"] = token
    return headers
