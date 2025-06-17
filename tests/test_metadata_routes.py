import json
from importlib import reload

import pytest
from backend import snowflake_client as sfc

import app as flask_app

@pytest.fixture()
def client(monkeypatch):
    # Ensure fresh Flask app context for each test
    reload(flask_app)
    flask_app.app.config['TESTING'] = True
    client = flask_app.app.test_client()

    dummy_list = ["A", "B"]

    monkeypatch.setattr(sfc.client, "list_databases", lambda: dummy_list)
    monkeypatch.setattr(sfc.client, "list_schemas", lambda db: [f"{db}_SC1", f"{db}_SC2"])
    monkeypatch.setattr(sfc.client, "list_roles", lambda: ["ROLE1", "ROLE2"])
    monkeypatch.setattr(sfc.client, "call_stored_procedure", lambda proc, args: {"success": True, "procedure": proc, "args": args})

    # Pretend OAuth is authenticated
    import backend.oauth as oauth
    monkeypatch.setattr(oauth, 'authenticated', lambda: True)
    monkeypatch.setattr(oauth, 'get_access_token', lambda: 'dummy-token')

    return client

def test_list_databases(client):
    resp = client.get("/databases")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["data"] == ["A", "B"]


def test_list_schemas_missing_param(client):
    resp = client.get("/schemas")
    assert resp.status_code == 400


def test_list_schemas_success(client):
    resp = client.get("/schemas?db=MYDB")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["data"] == ["MYDB_SC1", "MYDB_SC2"]


def test_list_roles(client):
    resp = client.get("/roles")
    assert resp.status_code == 200
    assert resp.get_json()["data"] == ["ROLE1", "ROLE2"]


def test_grant_permissions_read(client):
    payload = {
        "db": "DB1",
        "schema": "PUBLIC",
        "role": "DEV",
        "perm_type": "read",
    }
    resp = client.post("/grant_permissions", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True 