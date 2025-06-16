import jwt
from importlib import reload
import pytest
import app as flask_app

SECRET = 'x'

@pytest.fixture()
def client(monkeypatch):
    reload(flask_app)
    flask_app.app.config['TESTING'] = True
    client = flask_app.app.test_client()

    # Mock OAuth auth + token
    dummy_token = jwt.encode({'sub': 'ACCT.JDOE', 'role': 'DEV'}, SECRET, algorithm='HS256')

    import backend.oauth as oauth
    monkeypatch.setattr(oauth, 'authenticated', lambda: True)
    monkeypatch.setattr(oauth, 'get_access_token', lambda: dummy_token)

    with client.session_transaction() as sess:
        sess[oauth.TOKEN_KEY] = dummy_token
    return client

def test_userinfo_success(client):
    resp = client.get('/auth/userinfo')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['user'] == 'JDOE'
    assert data['role'] == 'DEV'
    assert data['can_grant'] is False 