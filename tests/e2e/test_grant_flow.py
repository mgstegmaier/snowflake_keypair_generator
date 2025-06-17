import threading
import time
from contextlib import contextmanager

import pytest

# Skip entire module if Playwright missing
playwright_mod = pytest.importorskip('playwright')
from playwright.sync_api import sync_playwright  # noqa: E402

# Import our Flask app
import app as flask_app  # noqa: E402


@contextmanager
def run_server(port: int = 5010):
    """Run the Flask app in a background thread for e2e tests."""
    flask_app.app.config.update(TESTING=False)

    def _run():
        flask_app.app.run(host="127.0.0.1", port=port, use_reloader=False)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    # Wait a bit for server to start
    time.sleep(1.5)
    try:
        yield
    finally:
        # Flask dev server stops when process exits (thread daemon)
        pass


auth_header = {"Authorization": "Bearer dummy"}

def _mock_metadata(monkeypatch):
    import backend.snowflake_client as sfc

    monkeypatch.setattr(sfc.client, "list_databases", lambda: ["DB1", "DB2"])
    monkeypatch.setattr(sfc.client, "list_schemas", lambda db: [f"{db}_SC1", f"{db}_SC2"])
    monkeypatch.setattr(sfc.client, "list_roles", lambda: ["ROLE1", "ROLE2"])
    monkeypatch.setattr(
        sfc.client,
        "call_stored_procedure",
        lambda proc, args: {"success": True, "procedure": proc, "args": args},
    )


@pytest.mark.skip(reason="E2E test requires complex setup that conflicts with GitHub Actions")
def test_grant_flow(monkeypatch):
    """Full browser flow: open grant tab, load dropdowns, grant perms, logout."""

    _mock_metadata(monkeypatch)

    # Force OAuth authenticated in app session
    import backend.oauth as oauth
    monkeypatch.setattr(oauth, 'authenticated', lambda: True)
    monkeypatch.setattr(oauth, 'get_access_token', lambda: 'dummy-token')

    with run_server():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Open index page
            page.goto("http://127.0.0.1:5010/")

            # Since real OAuth isn't available, manually set PAT via sessionStorage
            page.evaluate("window.sessionStorage.setItem('PAT', 'dummy');")

            # Click Grant tab
            page.click("#grant-tab")

            # Wait dropdowns
            page.wait_for_selector("#gpDatabase option")
            page.wait_for_selector("#gpRole option")

            # Select first options (already selected by default)
            # Click Grant
            page.click("#grantForm button[type='submit']")

            # Expect success toast
            page.wait_for_selector("text=Permissions granted!", timeout=3000)

            browser.close() 