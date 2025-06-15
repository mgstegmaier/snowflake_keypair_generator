"""Snowflake OAuth helper utilities."""

from __future__ import annotations

import os
import time
import secrets
import string
from urllib.parse import urlencode, quote
import json
import base64
import jwt
import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

import requests
from flask import session, redirect, url_for, request, jsonify

# Load environment variables
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")  # Now required for Basic Auth
OAUTH_AUTH_URL = os.getenv("OAUTH_AUTH_URL")
OAUTH_TOKEN_URL = os.getenv("OAUTH_TOKEN_URL")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:5001/oauth/callback")
OAUTH_SCOPE = os.getenv("OAUTH_SCOPE", "session:role:SYSADMIN")

# Print configuration for debugging
print("OAuth Configuration:")
print(f"OAUTH_CLIENT_ID: {OAUTH_CLIENT_ID}")
print(f"OAUTH_CLIENT_SECRET: {OAUTH_CLIENT_SECRET}")
print(f"OAUTH_AUTH_URL: {OAUTH_AUTH_URL}")
print(f"OAUTH_TOKEN_URL: {OAUTH_TOKEN_URL}")
print(f"OAUTH_REDIRECT_URI: {OAUTH_REDIRECT_URI}")
print(f"OAUTH_SCOPE: {OAUTH_SCOPE}")

STATE_KEY = "oauth_state"
TOKEN_KEY = "oauth_token"
REFRESH_KEY = "oauth_refresh"
EXP_KEY = "oauth_exp"

# Server-side state storage
_oauth_states = {}

def _gen_state(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def _clean_client_credentials(cred: str) -> str:
    """Remove quotes and trailing '=' from client credentials."""
    return cred.strip('"').rstrip('=')

def _generate_jwt():
    """Generate a JWT token for OAuth authentication."""
    # Use raw client ID and secret
    client_id = OAUTH_CLIENT_ID.strip('"')
    client_secret = OAUTH_CLIENT_SECRET.strip('"')
    print(f"Using client_id: {client_id}")
    print(f"Using client_secret: {client_secret}")
    
    # Get account locator from the URL
    account_locator = OAUTH_AUTH_URL.split('.')[0].split('//')[1]
    
    # Create JWT payload
    now = datetime.datetime.utcnow()
    payload = {
        'iss': client_id,
        'sub': f"{account_locator}.{client_id}",
        'iat': int(now.timestamp()),
        'exp': int((now + datetime.timedelta(seconds=30)).timestamp())
    }
    
    print(f"JWT payload: {payload}")
    
    # Sign the JWT with client secret
    try:
        token = jwt.encode(payload, client_secret, algorithm='HS256')
        print(f"Generated JWT: {token}")
        return token, None  # No public key needed when using client secret
    except Exception as e:
        print(f"Error generating JWT: {e}")
        return None, None

def build_authorize_url() -> str:
    state = _gen_state()
    print(f"Generated new state: {state}")
    
    # Store state in server-side dictionary
    _oauth_states[state] = time.time()
    print(f"Stored state in server memory: {state}")
    print(f"Current states: {_oauth_states}")
    
    # Use client ID exactly as provided
    client_id = OAUTH_CLIENT_ID.strip('"')
    print(f"Using client_id: {client_id}")
    
    # Build the URL manually to ensure proper scope encoding
    base_url = OAUTH_AUTH_URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "state": state,
        "scope": OAUTH_SCOPE
    }
    
    # Build query string
    query_string = urlencode(params)
    url = f"{base_url}?{query_string}"
    
    print(f"Generated authorize URL: {url}")
    return url

def exchange_code(code: str) -> bool:
    print(f"Exchanging code for token: {code}")
    state = request.args.get('state')
    print(f"State from request: {state}")
    print(f"Current states in memory: {_oauth_states}")
    
    # Verify state exists and is not expired (5 minutes)
    if state not in _oauth_states or time.time() - _oauth_states[state] > 300:
        print(f"Invalid or expired state: {state}")
        return False
    
    # Use client ID and secret exactly as provided
    client_id = OAUTH_CLIENT_ID.strip('"')
    client_secret = OAUTH_CLIENT_SECRET.strip('"')
    redirect_uri = OAUTH_REDIRECT_URI  # Send raw URI; form encoding will handle percent-encoding
    
    print(f"Using client_id: {client_id}")
    print(f"Using client_secret: {client_secret}")
    
    # Create Basic Auth header with client ID and secret
    auth_string = f"{client_id}:{client_secret}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    # Only include required fields in the request
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id
    }
    
    # Set headers with Basic Auth
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Authorization": f"Basic {auth_b64}"
    }
    
    print("\nToken Exchange Request:")
    print(f"URL: {OAUTH_TOKEN_URL}")
    print(f"Request Body (form-encoded): {urlencode(data)}")
    print(f"Request Body (raw): {data}")
    print(f"Headers: {headers}")
    
    try:
        resp = requests.post(
            OAUTH_TOKEN_URL,
            data=data,
            headers=headers,
            timeout=10
        )
        
        print(f"\nToken Exchange Response:")
        print(f"Status Code: {resp.status_code}")
        print(f"Headers: {dict(resp.headers)}")
        print(f"Body: {resp.text}")
        
        if resp.status_code != 200:
            print(f"Token exchange failed with status {resp.status_code}")
            try:
                error_data = resp.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except json.JSONDecodeError:
                print("Could not parse error response as JSON")
            return False
            
        try:
            payload = resp.json()
            print(f"Parsed response: {payload}")
            
            # Store tokens in session
            session[TOKEN_KEY] = payload["access_token"]
            session[REFRESH_KEY] = payload.get("refresh_token")
            expires_in = payload.get("expires_in", 3600)
            session[EXP_KEY] = time.time() + expires_in - 60  # refresh 1 min early
            session.modified = True
            
            # Clear the state after successful token exchange
            _oauth_states.pop(state, None)
            return True
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse response as JSON: {e}")
            return False
            
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return False

def refresh_token() -> bool:
    refresh = session.get(REFRESH_KEY)
    if not refresh:
        return False
    
    # Use client ID and secret exactly as provided
    client_id = OAUTH_CLIENT_ID.strip('"')
    client_secret = OAUTH_CLIENT_SECRET.strip('"')
    redirect_uri = OAUTH_REDIRECT_URI
    
    # Create Basic Auth header with client ID and secret
    auth_string = f"{client_id}:{client_secret}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    # Only include required fields in the request
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "redirect_uri": redirect_uri,
        "client_id": client_id
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Authorization": f"Basic {auth_b64}"
    }
    
    resp = requests.post(OAUTH_TOKEN_URL, data=data, headers=headers, timeout=10)
    if resp.status_code != 200:
        return False
        
    payload = resp.json()
    session[TOKEN_KEY] = payload["access_token"]
    session[REFRESH_KEY] = payload.get("refresh_token", refresh)
    expires_in = payload.get("expires_in", 3600)
    session[EXP_KEY] = time.time() + expires_in - 60
    return True

def get_access_token() -> str | None:
    token = session.get(TOKEN_KEY)
    if not token:
        return None
    if time.time() > session.get(EXP_KEY, 0):
        if not refresh_token():
            logout()
            return None
        token = session.get(TOKEN_KEY)
    return token

def logout() -> None:
    for k in (TOKEN_KEY, REFRESH_KEY, EXP_KEY):
        session.pop(k, None)
    session.modified = True

def authenticated() -> bool:
    """Check if the user is authenticated with a valid token."""
    return get_access_token() is not None 