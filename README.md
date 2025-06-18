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
