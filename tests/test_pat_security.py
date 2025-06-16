import time
import pytest
import app as flask_app

from importlib import reload

@pytest.fixture()
def client(monkeypatch):
    reload(flask_app)
    flask_app.app.config['TESTING'] = True
    client = flask_app.app.test_client()

    # Mock OAuth authenticated
    import backend.oauth as oauth
    monkeypatch.setattr(oauth, 'authenticated', lambda: True)
    monkeypatch.setattr(oauth, 'get_access_token', lambda: 'dummy-token')

    # Patch list_databases to avoid Snowflake dependency
    import backend.snowflake_client as sfc
    monkeypatch.setattr(sfc.client, 'list_databases', lambda: ['DBX'])

    return client

def test_inactivity_timeout(client):
    # First request should succeed, sets last_activity
    r1 = client.get('/databases')
    assert r1.status_code == 200

    # Fast-forward time beyond timeout
    import backend.security as sec
    expiry = sec.INACTIVITY_TIMEOUT_SECONDS + 1
    with client.session_transaction() as sess:
        sess['last_activity'] = sess.get('last_activity', time.time()) - expiry

    r2 = client.get('/databases')
    assert r2.status_code == 401
    assert 'expired' in r2.get_json()['error'] 