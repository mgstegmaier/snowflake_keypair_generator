# Snowflake Admin Console - Application Documentation

## Purpose

A **Snowflake Administration Web Application** designed to manage Snowflake users, RSA key pairs for authentication, and database/schema permissions. It provides a secure, audited interface for administrators to perform account management operations without direct SQL access.

---

## Architecture & Design

| Layer | Technology |
|-------|------------|
| **Frontend** | Single-page application (Bootstrap 5.3.2, vanilla JavaScript) |
| **Backend** | Python Flask 3.0.2 |
| **Database** | Snowflake (via `snowflake-connector-python`) |
| **Authentication** | Snowflake OAuth 2.0 with JWT token validation |
| **Security** | 15-minute inactivity timeout, role-based access control |

### Key Files

- `app.py` - Main Flask application
- `templates/index.html` - SPA frontend
- `backend/snowflake_client.py` - Snowflake connector
- `backend/oauth.py` - OAuth handling
- `backend/audit.py` - Audit logging

---

## User Management Tab

### Features

| Feature | Description |
|---------|-------------|
| **User Listing** | Displays all Snowflake users with search and filtering |
| **Filters** | Status (Active/Disabled/Locked), Key Status, Authentication type |
| **Pagination** | Configurable page sizes with auto-refresh |
| **Export** | CSV and JSON export options |

### User Information Displayed

- Username, Display Name, Email
- Account Status (Active/Disabled/Locked)
- RSA Key status (Has keys / No keys)
- MFA enabled, Password authentication status
- Creation date, Last successful login

### User Actions

| Action | Endpoint | Stored Procedure |
|--------|----------|------------------|
| **Unlock User** | `POST /users/<username>/unlock` | `sp_unlock_user` |
| **Reset Password** | `POST /users/<username>/reset_password` | `sp_reset_password` |
| **Unset Password** | `POST /users/<username>/unset_password` | `sp_unset_password` |
| **Set/Rotate RSA Key** | `POST /keys/users/<username>/set` | `sp_update_user_rsa_key` |
| **Get Key Details** | `GET /keys/users/<username>/details` | N/A (view query) |

### Data Source

Users retrieved from Snowflake view: `UPLAND_MAINTENANCE.SECURITY.V_USER_KEY_MANAGEMENT`

---

## Permissions Management Tab (Grant Permissions)

### Form Controls

- **Database Selection** - Dropdown of available databases
- **Schema Selection** - Dependent dropdown based on selected database
- **Role Selection** - Target role for permission grant/revoke
- **Warehouse Selection** - Required for stored procedure execution

### Permission Types

| Permission Type | Action | Stored Procedure |
|-----------------|--------|------------------|
| Read-Only Grant (Schema) | `read_grant_schema` | `sp_grant_read_perms(db, schema, role)` |
| Read-Only Grant (Database) | `read_grant_database` | `sp_grant_read_perms(db, '', role, TRUE)` |
| Read-Only Revoke (Schema) | `read_revoke_schema` | `sp_revoke_read_perms(db, schema, role)` |
| Read/Write Grant (Schema) | `readwrite_grant_schema` | `sp_grant_readwrite_perms(db, schema, role, FALSE)` |
| Read/Write Grant (Database) | `readwrite_grant_database` | `sp_grant_readwrite_perms(db, '', role, TRUE)` |
| Read/Write Revoke (Schema) | `readwrite_revoke_schema` | `sp_revoke_readwrite_perms(db, schema, role, FALSE)` |
| Read/Write Revoke (Database) | `readwrite_revoke_database` | `sp_revoke_readwrite_perms(db, '', role, TRUE)` |

### Access Control

Only users with roles in `ALLOW_GRANT_ROLES` (default: `SYSADMIN`, `SECURITYADMIN`) can grant permissions.

---

## Stored Procedures Reference

All stored procedures reside in `UPLAND_MAINTENANCE.SECURITY` schema.

### User Management Procedures

#### sp_unlock_user

```sql
CALL sp_unlock_user(p_username STRING)
```

**Purpose:** Unlock a locked user account

---

#### sp_reset_password

```sql
CALL sp_reset_password(p_username STRING, p_new_password STRING)
```

**Purpose:** Reset a user's password to a new value

---

#### sp_unset_password

```sql
CALL sp_unset_password(p_username STRING)
```

**Purpose:** Remove password authentication (sets `PASSWORD = NULL`)

---

#### sp_update_user_rsa_key

```sql
CALL sp_update_user_rsa_key(
    p_username          STRING,           -- Required
    p_rsa_public_key    STRING,           -- Required (PEM headers removed)
    p_unset_password    BOOLEAN DEFAULT FALSE,
    p_new_type          STRING  DEFAULT NULL  -- PERSON|SERVICE|LEGACY_SERVICE|NULL
)
```

**Purpose:** Set/rotate RSA public key with optional password unset and user type change

**Language:** JavaScript

**Execution:** `EXECUTE AS OWNER`

---

### Permission Management Procedures

#### sp_grant_read_perms

```sql
CALL sp_grant_read_perms(p_database STRING, p_schema STRING, p_role STRING [, p_database_level BOOLEAN])
```

**Purpose:** Grant read-only permissions on database or schema

---

#### sp_revoke_read_perms

```sql
CALL sp_revoke_read_perms(p_database STRING, p_schema STRING, p_role STRING)
```

**Purpose:** Revoke read-only permissions

---

#### sp_grant_readwrite_perms

```sql
CALL sp_grant_readwrite_perms(p_database STRING, p_schema STRING, p_role STRING, p_database_level BOOLEAN)
```

**Purpose:** Grant read/write permissions on database or schema

---

#### sp_revoke_readwrite_perms

```sql
CALL sp_revoke_readwrite_perms(p_database STRING, p_schema STRING, p_role STRING, p_database_level BOOLEAN)
```

**Purpose:** Revoke read/write permissions

---

## API Endpoints (User & Permissions Only)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/users` | List all users |
| `POST` | `/users/<username>/unlock` | Unlock user |
| `POST` | `/users/<username>/reset_password` | Reset password |
| `POST` | `/users/<username>/unset_password` | Unset password |
| `GET` | `/keys/users` | List users with key info |
| `GET` | `/keys/users/<username>/details` | Get user key details |
| `POST` | `/keys/users/<username>/set` | Set/update RSA key |
| `POST` | `/keys/users/<username>/unset` | Remove RSA key |
| `POST` | `/grant_permissions` | Grant/revoke permissions |
| `GET` | `/databases` | List databases |
| `GET` | `/schemas` | List schemas |
| `GET` | `/roles` | List roles |
| `GET` | `/warehouses` | List warehouses |

---

## Security Features

- **OAuth 2.0** authentication via Snowflake
- **Role-based access** - Permission grants restricted to SYSADMIN/SECURITYADMIN
- **15-minute inactivity timeout** with automatic session termination
- **SQL injection prevention** - Identifier validation, parameterized queries
- **Comprehensive audit logging** - All actions logged to `logs/audit/audit_YYYY-MM-DD.jsonl`
