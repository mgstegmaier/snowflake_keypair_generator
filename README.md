# Snowflake Key Pair Generator

A web-based application for generating Snowflake key pairs with a user-friendly interface.

## Features
- Generate encrypted or unencrypted key pairs
- Automatic file downloads
- Copy Snowflake ALTER USER command to clipboard
- Option to create processed key file
- Secure passphrase storage
- Automatic cleanup of temporary files
- Modern, responsive UI

## Installation

### Quick Start
Simply run:
```bash
python3 setup.py
python3 app.py
```
This will:
1. Check and install required packages if needed
2. Start the application
3. Automatically open your default web browser

### Manual Installation
If you prefer to install manually:

1. Create a virtual environment (optional but recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Security Configuration

### Flask SECRET_KEY Setup (Required for Production)

The Flask SECRET_KEY is critical for application security and is used for:
- **Session Security**: Cryptographically signing session cookies to prevent tampering
- **CSRF Protection**: Generating and validating Cross-Site Request Forgery tokens
- **Cookie Integrity**: Ensuring secure cookies haven't been modified client-side
- **OAuth Token Protection**: Securing Snowflake authentication tokens in sessions

#### Setting Up Your SECRET_KEY

**Option 1: Using .env file (Recommended)**
1. Create a `.env` file in your project root:
```bash
# .env file
FLASK_SECRET_KEY=your-64-character-secret-key-here
```

2. The application will automatically load this when it starts.

**Option 2: Environment Variable**
```bash
export FLASK_SECRET_KEY="your-64-character-secret-key-here"
```

**Option 3: System Environment (Production)**
Set the environment variable in your deployment system (Docker, systemd, etc.)

#### Generating a Secure SECRET_KEY

**Method 1: Python (Recommended)**
```python
import secrets
print(secrets.token_urlsafe(48))  # Generates ~64 character URL-safe string
```

**Method 2: OpenSSL**
```bash
openssl rand -base64 48 | tr -d '\n'
```

**Method 3: System Random (Linux/macOS)**
```bash
head -c 48 /dev/urandom | base64 | tr -d '\n'
```

#### Security Requirements
- **Minimum Length**: 32 characters
- **Recommended Length**: 64+ characters
- **Character Set**: Use letters, numbers, and URL-safe characters
- **Uniqueness**: Generate a unique key for each deployment
- **Secrecy**: Never commit SECRET_KEY to version control

#### Development vs Production
- **Development**: Application will use a default key with security warnings
- **Production**: **MUST** set a secure SECRET_KEY via environment variable
- **Warning**: Using the default key in production creates critical security vulnerabilities

### Environment Variables Summary
```bash
# Required for production
FLASK_SECRET_KEY=your-generated-secret-key

# OAuth Configuration (if using Snowflake integration)
OAUTH_CLIENT_ID=your-snowflake-oauth-client-id
OAUTH_CLIENT_SECRET=your-snowflake-oauth-client-secret
OAUTH_AUTH_URL=your-snowflake-oauth-auth-url
OAUTH_TOKEN_URL=your-snowflake-oauth-token-url
```

### .env File Template

Create a `.env` file in your project root directory and populate it with your specific values:

```bash
# =============================================================================
# Snowflake Administration App - Environment Configuration
# =============================================================================
# Copy this template to .env and fill in your actual values
# IMPORTANT: Never commit .env files to version control!

# -----------------------------------------------------------------------------
# Flask Application Security (REQUIRED)
# -----------------------------------------------------------------------------
# Generate a secure 64+ character secret key for Flask session security
# Use: python -c "import secrets; print(secrets.token_urlsafe(48))"
FLASK_SECRET_KEY=your-64-character-secret-key-here

# Alternative variable name (for backward compatibility)
# SECRET_KEY=your-64-character-secret-key-here

# -----------------------------------------------------------------------------
# Snowflake OAuth Configuration (REQUIRED for full functionality)
# -----------------------------------------------------------------------------
# OAuth Client ID from your Snowflake OAuth integration
OAUTH_CLIENT_ID=your-snowflake-oauth-client-id

# OAuth Client Secret from your Snowflake OAuth integration
OAUTH_CLIENT_SECRET=your-snowflake-oauth-client-secret

# Snowflake OAuth authorization URL
# Format: https://your-account.snowflakecomputing.com/oauth/authorize
OAUTH_AUTH_URL=https://your-account.snowflakecomputing.com/oauth/authorize

# Snowflake OAuth token URL
# Format: https://your-account.snowflakecomputing.com/oauth/token-request
OAUTH_TOKEN_URL=https://your-account.snowflakecomputing.com/oauth/token-request

# OAuth redirect URI (should match your app's callback URL)
OAUTH_REDIRECT_URI=http://localhost:5001/oauth/callback

# OAuth scope (defines permissions and role)
OAUTH_SCOPE=session:role:SYSADMIN

# -----------------------------------------------------------------------------
# Snowflake Connection Configuration (OPTIONAL - for direct connections)
# -----------------------------------------------------------------------------
# Your Snowflake account identifier
SNOWFLAKE_ACCOUNT=your-account.snowflakecomputing.com

# Default Snowflake user for administrative operations
SNOWFLAKE_USER=your-admin-user

# Default Snowflake role for operations
SNOWFLAKE_ROLE=SYSADMIN

# Default warehouse for query execution
SNOWFLAKE_WAREHOUSE=your-default-warehouse

# -----------------------------------------------------------------------------
# Permission Management Configuration (OPTIONAL)
# -----------------------------------------------------------------------------
# Comma-separated list of roles allowed to grant permissions
ALLOW_GRANT_ROLES=SYSADMIN,SECURITYADMIN

# -----------------------------------------------------------------------------
# Development/Debug Settings (OPTIONAL)
# -----------------------------------------------------------------------------
# Set to 'True' to enable Flask debug mode (development only!)
# FLASK_DEBUG=False

# Set to 'development' or 'production'
# FLASK_ENV=development

# Custom port for the Flask application (default: 5001)
# FLASK_PORT=5001
```

#### .env File Setup Instructions

1. **Copy the template above** into a new file named `.env` in your project root
2. **Replace all placeholder values** with your actual Snowflake and application configuration
3. **Generate a secure SECRET_KEY** using one of the methods in the previous section
4. **Add .env to your .gitignore** to prevent committing secrets to version control
5. **Set appropriate file permissions** (e.g., `chmod 600 .env` on Unix systems)

#### Required vs Optional Variables

**Required for Basic Functionality:**
- `FLASK_SECRET_KEY` - Essential for session security

**Required for Full Snowflake Integration:**
- `OAUTH_CLIENT_ID` - Your Snowflake OAuth client ID
- `OAUTH_CLIENT_SECRET` - Your Snowflake OAuth client secret
- `OAUTH_AUTH_URL` - Your Snowflake OAuth authorization endpoint
- `OAUTH_TOKEN_URL` - Your Snowflake OAuth token endpoint

**Optional (with sensible defaults):**
- `OAUTH_REDIRECT_URI` - Defaults to `http://localhost:5001/oauth/callback`
- `OAUTH_SCOPE` - Defaults to `session:role:SYSADMIN`
- `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE` - For direct connections
- `ALLOW_GRANT_ROLES` - Defaults to `SYSADMIN,SECURITYADMIN`

## Usage

1. Start the application:
```bash
python3 app.py
```

2. The application will automatically open in your default web browser at `http://localhost:5001`

3. Follow the on-screen instructions to generate your key pair:
   - Enter your Snowflake username
   - Choose whether to encrypt the private key
   - Enter a passphrase if encryption is enabled
   - Choose whether to create a processed key file
   - Click "Generate Key Pair"
   - Download the generated files using the download buttons

## Requirements
- Python 3.6 or higher
- OpenSSL (for key generation)
- Modern web browser

## Data Retention & Security

This application is designed with **zero long-term data retention** and follows strict security principles to ensure sensitive data is never persisted beyond active user sessions.

### Data Retention Conditions

#### 1. Snowflake Data Retrieval & Caching
The application retrieves data from Snowflake under these conditions:
- **User Management Data**: Retrieved via optimized view `V_USER_KEY_MANAGEMENT` and cached in server memory
- **Database/Schema Lists**: Retrieved on-demand for grant permissions functionality  
- **Role Information**: Retrieved and cached for role management operations
- **Key Management Data**: Retrieved from Snowflake views for RSA key information

#### 2. Data Removal from Browser/Session Memory
Data is automatically cleared from browser session memory under these conditions:

**Automatic Session Expiry:**
- **15-minute inactivity timeout**: If no user activity (mouse, keyboard, touch) for 15 minutes
- **OAuth token expiration**: When OAuth tokens expire (typically 1 hour, refreshed automatically)
- **Manual logout**: When user explicitly logs out
- **Tab/browser close**: All session data cleared immediately

**Session Cleanup Implementation:**
- Frontend inactivity timer monitors user activity
- Backend session validation with automatic cleanup
- All OAuth tokens and session data cleared on expiry

#### 3. Temporary File Management
**Generated Key Files** are automatically managed:
- **Storage Location**: `tempfile.gettempdir()/snowflake_keys/{username}/`
- **Automatic Cleanup**: Files removed via cleanup endpoint after download
- **Security**: Private keys never stored server-side, only processed client-side

#### 4. OAuth Token Management
**OAuth tokens are cleared when:**
- Session expires due to inactivity (15 minutes)
- User manually logs out
- Token refresh fails
- Application restart
- Connection errors occur

#### 5. Server-Side Cache Management
**Snowflake data cache is cleared when:**
- Connection is closed or fails
- Manual cache clear via admin endpoint
- Application restart
- Session timeout occurs

### Security Design Principles

**✅ Memory-Only Data Storage:**
- OAuth tokens stored in Flask session (server-side memory only)
- User data cached temporarily for performance optimization
- Generated passphrases displayed once then immediately cleared

**✅ No Persistent Storage:**
- No localStorage or persistent browser storage used
- No database storage of sensitive authentication data
- Private keys never stored server-side (only processed client-side)

**✅ Automatic Security Cleanup:**
- 15-minute inactivity timeout with automatic session termination
- Temporary file cleanup after key generation operations
- Comprehensive session expiration handling
- OAuth token lifecycle management

**✅ Zero Long-Term Retention:**
All Snowflake data exists only:
1. **In server memory** during active sessions (cleared on inactivity/logout)
2. **In temporary files** during key generation (manually cleaned up post-download)
3. **In browser session** during active use (cleared on tab close/inactivity)

### Data Privacy Guarantee
The system prioritizes security by ensuring **no sensitive data persists beyond the active user session**. All authentication tokens, user data, and generated keys follow the principle of minimal data retention with multiple automatic cleanup mechanisms to protect user privacy and security.
