# Data Privacy & Security Analysis
**Snowflake Administration Web Application**

---

## Application Overview

### System Purpose
The Snowflake Administration Web Application is a Flask-based web interface designed to streamline Snowflake database administration tasks. It provides a unified dashboard for managing users, roles, permissions, and RSA key pairs without requiring direct SQL command execution or Snowflake console access.

### Core Functionality
- **User Management**: View, unlock, and manage Snowflake user accounts with comprehensive status tracking
- **Role Management**: Administer roles, view privileges, and manage role assignments
- **Permission Granting**: Automated database and schema permission management via stored procedures
- **RSA Key Management**: Generate, set, and rotate RSA key pairs for Snowflake user authentication
- **Key Generation**: Browser-based RSA key pair generation with optional encryption

### Architecture Overview
```
Browser (Bootstrap 5 + Vanilla JS) 
    ↓ OAuth 2.0 Authentication
Flask Backend (Python 3.13)
    ↓ Session-based Authentication  
Snowflake Connector (snowflake-connector-python)
    ↓ DEFINER'S RIGHTS Stored Procedures
Snowflake Database (User/Role/Permission Management)
```

### Technical Stack
- **Backend**: Flask 3.x with Python 3.13
- **Authentication**: Snowflake OAuth 2.0 with JWT tokens
- **Frontend**: Jinja2 templates, Bootstrap 5, vanilla JavaScript
- **Database**: Snowflake connector with optimized view-based queries
- **Security**: Session-based authentication with inactivity timeouts

---

## Data Retention & Security Conditions

### Data Retention Policy: Zero Long-Term Retention

This application is designed with **zero long-term data retention** and follows strict security principles to ensure sensitive data is never persisted beyond active user sessions.

### 1. Snowflake Data Retrieval & Caching

**Data Retrieved from Snowflake:**
- **User Management Data**: Retrieved via optimized view `V_USER_KEY_MANAGEMENT` and cached in server memory
- **Database/Schema Lists**: Retrieved on-demand for grant permissions functionality  
- **Role Information**: Retrieved and cached for role management operations
- **Key Management Data**: Retrieved from Snowflake views for RSA key information

**Server-Side Caching Implementation:**
```python
# In snowflake_client.py
self._users_cache: Dict[str, Dict[str, Any]] = {}  # Cache for user data by username
self._cache_timestamp: float | None = None  # When cache was last updated
```

### 2. Data Removal from Browser/Session Memory

**Automatic Session Expiry Conditions:**
- **15-minute inactivity timeout**: If no user activity (mouse, keyboard, touch) for 15 minutes
- **OAuth token expiration**: When OAuth tokens expire (typically 1 hour, refreshed automatically)
- **Manual logout**: When user explicitly logs out
- **Tab/browser close**: All session data cleared immediately

**Session Cleanup Implementation:**
- Frontend inactivity timer monitors user activity every 60 seconds
- Backend session validation with automatic cleanup via `@require_oauth` decorator
- All OAuth tokens and session data cleared on expiry
- No localStorage or persistent browser storage used

### 3. Temporary File Management

**Generated Key Files Management:**
- **Storage Location**: `tempfile.gettempdir()/snowflake_keys/{username}/`
- **Automatic Cleanup**: Files removed via `/cleanup/<username>` endpoint after download
- **Security**: Private keys never stored server-side, only processed client-side
- **Session Isolation**: Each user gets isolated temporary directory

### 4. OAuth Token Management

**OAuth tokens are cleared when:**
- Session expires due to inactivity (15 minutes)
- User manually logs out via `/auth/logout` endpoint
- Token refresh fails (automatic logout triggered)
- Application restart (all server-side sessions cleared)
- Connection errors occur

**Token Storage Pattern:**
```python
# Server-side Flask session only
session[TOKEN_KEY] = payload["access_token"]
session[REFRESH_KEY] = payload.get("refresh_token")
session[EXP_KEY] = time.time() + expires_in - 60
```

### 5. Server-Side Cache Management

**Snowflake data cache is cleared when:**
- Connection is closed or fails: `self._users_cache = {}`
- Manual cache clear via `/debug/clear-cache` endpoint
- Application restart (all in-memory data lost)
- Session timeout occurs

### Data Privacy Guarantee

**✅ Memory-Only Data Storage:**
- OAuth tokens stored in Flask session (server-side memory only)
- User data cached temporarily for performance optimization
- Generated passphrases displayed once then immediately cleared

**✅ No Persistent Storage:**
- No localStorage or persistent browser storage used
- No database storage of sensitive authentication data
- Private keys never stored server-side (only processed client-side)

**✅ Zero Long-Term Retention:**
All Snowflake data exists only:
1. **In server memory** during active sessions (cleared on inactivity/logout)
2. **In temporary files** during key generation (manually cleaned up post-download)
3. **In browser session** during active use (cleared on tab close/inactivity)

---

## Security Vulnerability Analysis

### Critical Vulnerabilities Identified

#### 1. **CRITICAL: Hardcoded Development Secret Key**
**Location**: `app.py:20`
```python
app.config['SECRET_KEY'] = 'dev-secret-key-123'  # In production, use a secure random key
```

**Risk Level**: **CRITICAL**
- **Impact**: Session hijacking, CSRF attacks, authentication bypass
- **Conditions**: Any deployment using this hardcoded key is vulnerable
- **Data at Risk**: All session data, OAuth tokens, user authentication state

**Mitigation**:
- Use environment variable: `app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')`
- Generate cryptographically secure random key for production
- Implement key rotation strategy
- Add startup validation to ensure production key is set

#### 2. **HIGH: Shell Injection Vulnerability in Key Generation**
**Location**: `app.py:42`, `generate_key_pair.py:10`
```python
result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
```

**Risk Level**: **HIGH**
- **Impact**: Remote code execution, server compromise
- **Conditions**: If username input contains shell metacharacters
- **Data at Risk**: Entire server filesystem, all cached data

**Current Mitigation**: Username appears to be validated, but not explicitly sanitized

**Enhanced Mitigation**:
```python
# Use shell=False and pass arguments as list
result = subprocess.run([
    'openssl', 'genrsa', '2048'
], check=True, capture_output=True, text=True)
```
- Implement strict input validation for usernames
- Use shell=False with argument lists
- Add allowlist validation for username patterns

#### 3. **MEDIUM: SQL Injection in User Queries**
**Location**: `backend/snowflake_client.py:330`
```python
cur.execute(f"SELECT * FROM UPLAND_MAINTENANCE.SECURITY.V_USER_KEY_MANAGEMENT WHERE USERNAME = '{username}'")
```

**Risk Level**: **MEDIUM**
- **Impact**: Data extraction, potential privilege escalation
- **Conditions**: If username parameter contains SQL injection payloads
- **Data at Risk**: All user data in Snowflake database

**Mitigation**:
```python
# Use parameterized queries
cur.execute("SELECT * FROM UPLAND_MAINTENANCE.SECURITY.V_USER_KEY_MANAGEMENT WHERE USERNAME = %s", (username,))
```

#### 4. **MEDIUM: Information Disclosure in Logs**
**Location**: Multiple locations with token logging
```python
print(f"Token exchange failed: {resp.status_code} - {resp.text}")
logger.info('Opening Snowflake connection as %s role=%s warehouse=%s token=%s', user, role, warehouse, _redact(token))
```

**Risk Level**: **MEDIUM**
- **Impact**: Sensitive token exposure in logs
- **Conditions**: Debug logging enabled, log file access
- **Data at Risk**: OAuth tokens, authentication credentials

**Current Mitigation**: Some token redaction implemented
**Enhanced Mitigation**: Ensure all token logging is properly redacted

#### 5. **LOW: Session Fixation Potential**
**Location**: OAuth implementation
**Risk Level**: **LOW**
- **Impact**: Session hijacking under specific conditions
- **Conditions**: Attacker can predict or control session tokens
- **Mitigation**: Flask session management appears secure, but consider explicit session regeneration on login

### Secure Implementation Patterns Identified

#### ✅ **Proper Authentication Middleware**
```python
@require_oauth
def wrapper(*args, **kwargs):
    if not oauth.authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    # Inactivity timeout check
    if (now - last) > sec.INACTIVITY_TIMEOUT_SECONDS:
        session.clear()
```

#### ✅ **Secure OAuth State Management**
```python
# Server-side state storage with expiration
_oauth_states = {}
if state not in _oauth_states or time.time() - _oauth_states.get(state, 0) > 300:
    return False
```

#### ✅ **Proper Session Cleanup**
```python
def logout() -> None:
    for k in (TOKEN_KEY, REFRESH_KEY, EXP_KEY, STATE_KEY):
        session.pop(k, None)
    session.modified = True
```

#### ✅ **Inactivity Timeout Implementation**
- 15-minute inactivity timeout with automatic session termination
- Client-side activity monitoring with server-side validation
- Automatic cleanup of all session data on timeout

---

## Data Breach Risk Assessment

### High-Risk Scenarios

#### 1. **Server Compromise via Shell Injection**
**Likelihood**: Medium (if username validation fails)
**Impact**: Critical (full server access)
**Data at Risk**: All cached user data, OAuth tokens, temporary key files
**Mitigation Priority**: **IMMEDIATE**

#### 2. **Session Hijacking via Hardcoded Secret**
**Likelihood**: High (in current configuration)
**Impact**: High (user impersonation, data access)
**Data at Risk**: All user session data, authentication state
**Mitigation Priority**: **IMMEDIATE**

#### 3. **Database Injection via SQL Queries**
**Likelihood**: Low (requires malicious username)
**Impact**: Medium (data extraction)
**Data at Risk**: Snowflake user database contents
**Mitigation Priority**: **HIGH**

### Low-Risk Scenarios

#### 1. **Log File Exposure**
**Likelihood**: Low (requires server access)
**Impact**: Medium (token exposure)
**Data at Risk**: OAuth tokens in log files
**Mitigation Priority**: **MEDIUM**

#### 2. **Memory Dump Analysis**
**Likelihood**: Very Low (requires root access)
**Impact**: Medium (cached data exposure)
**Data at Risk**: In-memory user cache, session data
**Mitigation Priority**: **LOW**

---

## Compliance & Security Recommendations

### Immediate Actions Required

1. **Replace Hardcoded Secret Key**
   - Generate cryptographically secure secret key
   - Store in environment variable
   - Implement startup validation

2. **Fix Shell Injection Vulnerability**
   - Replace `shell=True` with argument lists
   - Implement strict username validation
   - Add input sanitization

3. **Implement Parameterized Queries**
   - Replace string formatting with parameterized queries
   - Add SQL injection prevention patterns

### Security Enhancements

1. **Enhanced Logging Security**
   - Ensure all sensitive data is redacted in logs
   - Implement structured logging with security levels
   - Add log rotation and secure storage

2. **Input Validation Framework**
   - Implement comprehensive input validation
   - Add allowlist patterns for usernames
   - Validate all user inputs before processing

3. **Security Headers**
   - Add Content Security Policy (CSP)
   - Implement X-Frame-Options, X-Content-Type-Options
   - Add Strict-Transport-Security for HTTPS

4. **Session Security**
   - Implement session regeneration on login
   - Add CSRF protection for state-changing operations
   - Consider shorter session timeouts for high-privilege operations

### Monitoring & Alerting

1. **Security Event Monitoring**
   - Log authentication failures and suspicious activity
   - Monitor for SQL injection attempts
   - Alert on unusual session patterns

2. **Data Access Logging**
   - Log all Snowflake data access
   - Monitor cache hit/miss patterns
   - Track user privilege escalation attempts

---

## Conclusion

The Snowflake Administration Web Application implements strong data privacy principles with zero long-term retention and comprehensive session management. However, several critical security vulnerabilities require immediate attention, particularly the hardcoded secret key and shell injection risks.

**Security Posture**: **REQUIRES IMMEDIATE REMEDIATION**
**Data Privacy Compliance**: **EXCELLENT** (zero retention policy)
**Production Readiness**: **BLOCKED** (pending critical vulnerability fixes)

### Recommended Review Process

1. **Immediate Security Fixes**: Address critical and high-risk vulnerabilities
2. **Security Testing**: Conduct penetration testing after fixes
3. **Code Review**: Implement secure coding review process
4. **Production Deployment**: Deploy only after security validation

This document provides the foundation for security team review and remediation planning. 