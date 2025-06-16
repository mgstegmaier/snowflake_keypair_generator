# Tech Context

| Area | Stack |
|------|-------|
| Language | Python 3.13 |
| Framework | Flask 3.x |
| Auth | Snowflake OAuth 2.0 (client credentials with HS256), Flask-Session |
| DB SDK | `snowflake-connector-python` |
| Front-end | Jinja2 templates, Bootstrap 5, vanilla JS |
| Testing | pytest, monkeypatch, Playwright (planned) |
| Linting | Ruff |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |

### Dev Setup
1. `python -m venv .venv && source .venv/bin/activate`  
2. `pip install -r requirements.txt -r requirements-dev.txt`  
3. Set env vars (`OAUTH_*`, `SNOWFLAKE_*`).  
4. `flask run` (opens at http://127.0.0.1:5001).

### Constraints / Notes
• Must avoid persisting private keys on server.  
• Only public key is downloadable; private key stays client-side.  
• Snowflake account, user, and warehouse default via env vars but can be overridden. 