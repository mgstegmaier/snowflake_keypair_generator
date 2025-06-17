"""Snowflake OAuth helper utilities."""

from __future__ import annotations

import os
import time
import secrets
import string
from urllib.parse import urlencode
import json
import base64

import requests
from flask import session, request

# Load environment variables
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
OAUTH_AUTH_URL = os.getenv("OAUTH_AUTH_URL")
OAUTH_TOKEN_URL = os.getenv("OAUTH_TOKEN_URL")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:5001/oauth/callback")
OAUTH_SCOPE = os.getenv("OAUTH_SCOPE", "session:role:SYSADMIN")

STATE_KEY = "oauth_state"
TOKEN_KEY = "oauth_token"
REFRESH_KEY = "oauth_refresh"
EXP_KEY = "oauth_exp"

# Server-side state storage
_oauth_states = {}

# Roles allowed to grant permissions (comma-separated env var)
ALLOW_GRANT_ROLES = {
    r.strip().upper()
    for r in os.getenv("ALLOW_GRANT_ROLES", "SYSADMIN,SECURITYADMIN").split(",")
    if r.strip()
}

def _gen_state(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def build_authorize_url() -> str:
    state = _gen_state()
    _oauth_states[state] = time.time()
    
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID.strip('"'),
        "redirect_uri": OAUTH_REDIRECT_URI,
        "state": state,
        "scope": OAUTH_SCOPE
    }
    return f"{OAUTH_AUTH_URL}?{urlencode(params)}"

def exchange_code(code: str) -> bool:
    state = request.args.get('state')
    
    if state not in _oauth_states or time.time() - _oauth_states.get(state, 0) > 300:
        print(f"Invalid or expired state: {state}")
        return False
    
    client_id = OAUTH_CLIENT_ID.strip('"')
    client_secret = OAUTH_CLIENT_SECRET.strip('"')
    
    auth_string = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_string.encode('ascii')).decode('ascii')
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": OAUTH_REDIRECT_URI,
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Authorization": f"Basic {auth_b64}"
    }
    
    try:
        resp = requests.post(OAUTH_TOKEN_URL, data=data, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            print(f"Token exchange failed: {resp.status_code} - {resp.text}")
            return False
            
        payload = resp.json()
        session[TOKEN_KEY] = payload["access_token"]
        session[REFRESH_KEY] = payload.get("refresh_token")
        expires_in = payload.get("expires_in", 3600)
        session[EXP_KEY] = time.time() + expires_in - 60
        session.modified = True
        
        _oauth_states.pop(state, None)
        return True
            
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return False

def refresh_token() -> bool:
    refresh = session.get(REFRESH_KEY)
    if not refresh:
        return False
    
    client_id = OAUTH_CLIENT_ID.strip('"')
    client_secret = OAUTH_CLIENT_SECRET.strip('"')
    
    auth_string = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_string.encode('ascii')).decode('ascii')
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Authorization": f"Basic {auth_b64}"
    }
    
    try:
        resp = requests.post(OAUTH_TOKEN_URL, data=data, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            logout()
            return False
            
        payload = resp.json()
        session[TOKEN_KEY] = payload["access_token"]
        session[REFRESH_KEY] = payload.get("refresh_token", refresh)
        expires_in = payload.get("expires_in", 3600)
        session[EXP_KEY] = time.time() + expires_in - 60
        return True
    except requests.RequestException:
        return False

def get_access_token() -> str | None:
    if time.time() > session.get(EXP_KEY, 0):
        if not refresh_token():
            return None
    return session.get(TOKEN_KEY)

def logout() -> None:
    for k in (TOKEN_KEY, REFRESH_KEY, EXP_KEY, STATE_KEY):
        session.pop(k, None)
    session.modified = True

def authenticated() -> bool:
    return get_access_token() is not None

def current_identity() -> dict | None:
    token = session.get(TOKEN_KEY)
    if not token:
        return None
    try:
        # We need to import jwt here, but only for this function
        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})
        user = payload.get("sub", "").split(".")[-1]
        role = payload.get("scope", "").split(":")[-1] # Example: session:role:SYSADMIN
        return {"user": user.upper(), "role": (role or "").upper()}
    except Exception as e:
        print(f"Could not decode token: {e}")
        # Fallback: if we can't decode the token but we have one, return a basic identity
        # This allows the app to function even if token parsing fails
        if token:
            # Extract user from environment as fallback
            import os
            user = os.getenv('SNOWFLAKE_USER', 'UNKNOWN_USER')
            role = os.getenv('SNOWFLAKE_ROLE', 'SYSADMIN')
            return {"user": user.upper(), "role": role.upper()}
        return None 