"""snowflake_client.py

Thin wrapper around the Snowflake Python connector.
Phase-0: skeleton only, with no real execution logic.  Later phases will
implement connection pooling and stored-procedure execution helpers.
"""

from __future__ import annotations

from typing import Any, Dict, List
import time
import re

try:
    import snowflake.connector  # type: ignore
except ImportError:  # pragma: no cover
    # Snowflake connector not yet installed in all dev environments.
    snowflake = None  # type: ignore


class SnowflakeClient:
    """Deferred-init client.

    The actual connection is established lazily once :py:meth:`connect` is called.
    """

    def __init__(self) -> None:
        self._conn: "snowflake.connector.SnowflakeConnection | None" = None
        self._warehouse: str | None = None
        self._users_cache: Dict[str, Dict[str, Any]] = {}  # Cache for user data by username
        self._cache_timestamp: float | None = None  # When cache was last updated

    def _validate_identifier(self, identifier: str, identifier_type: str = "identifier") -> None:
        """Validate Snowflake identifiers to prevent SQL injection.
        
        Snowflake identifiers must match: ^[A-Za-z_][A-Za-z0-9_$]*$
        or be properly quoted.
        """
        if not identifier:
            raise ValueError(f"Invalid {identifier_type}: empty string")
        
        # Allow quoted identifiers (enclosed in double quotes)
        if identifier.startswith('"') and identifier.endswith('"'):
            # Check for proper escaping of quotes inside quoted identifier
            inner = identifier[1:-1]
            if '""' in inner:
                # Properly escaped quote, replace with single quote for validation
                inner = inner.replace('""', '"')
            if '"' in inner:
                raise ValueError(f"Invalid {identifier_type}: unescaped quote in quoted identifier")
            return  # Quoted identifiers are accepted as-is after quote validation
        
        # Unquoted identifiers must match Snowflake naming rules
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_$]*$', identifier):
            raise ValueError(f"Invalid {identifier_type}: must contain only letters, numbers, underscore, and dollar sign, and start with letter or underscore")
        
        # Additional length check (Snowflake max identifier length is 255)
        if len(identifier) > 255:
            raise ValueError(f"Invalid {identifier_type}: too long (max 255 characters)")

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    def connect(self, *, pat: str, account: str, user: str, warehouse: str, role: str) -> None:
        """Open a connection.

        Parameters mirror ``snowflake.connector.connect``.  In later phases we'll
        inject the PAT via ``authenticator="OAUTH"`` and pass the token.
        """
        if snowflake is None:
            raise RuntimeError("snowflake-connector-python not installed.")
        if self._conn is not None:
            return  # Already connected
        self._conn = snowflake.connector.connect(
            account=account,
            user=user,
            authenticator="oauth",
            token=pat,
            warehouse=warehouse,
            role=role,
        )
        self._warehouse = warehouse

        # Explicitly activate warehouse to avoid 000606 errors
        if warehouse:
            cur = self._conn.cursor()
            try:
                # Validate warehouse name to prevent SQL injection
                self._validate_identifier(warehouse, "warehouse")
                cur.execute(f"USE WAREHOUSE {warehouse}")  # Note: USE statements require identifier, not parameter
            except Exception:
                # Ignore errors such as warehouse not found; caller may set another warehouse
                pass
            finally:
                cur.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        # Clear cache when connection is closed
        self._users_cache = {}
        self._cache_timestamp = None

    # ------------------------------------------------------------------
    # Stored-procedure execution – placeholders for now
    # ------------------------------------------------------------------
    def call_stored_procedure(self, proc_name: str, args: List[Any]) -> Dict[str, Any]:
        """Call a stored procedure by name.

        Phase-0 stub: returns a fake response.  Real execution logic will be
        added in Phase-2+.
        """
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        cur = self._conn.cursor()
        try:
            # Debug: Show current context
            cur.execute("SELECT CURRENT_ROLE(), CURRENT_USER(), CURRENT_WAREHOUSE()")
            context = cur.fetchone()
            print(f"Current context - Role: {context[0]}, User: {context[1]}, Warehouse: {context[2]}")
            
            print(f"Calling stored procedure: {proc_name} with args: {args}")
            result = cur.callproc(proc_name, args)
            print(f"Stored procedure result: {result}")
            
            # Try to fetch any result set from the stored procedure
            try:
                rows = cur.fetchall()
                if rows:
                    print(f"Stored procedure returned {len(rows)} rows: {rows}")
                    return {"success": True, "result": result, "rows": rows}
            except Exception as e:
                print(f"No result set to fetch (this is normal): {e}")
            
            return {"success": True, "result": result}
        except Exception as e:
            print(f"Error calling stored procedure {proc_name}: {e}")
            raise
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Metadata fetch helpers
    # ------------------------------------------------------------------
    def list_databases(self) -> List[str]:
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        cur = self._conn.cursor()
        try:
            cur.execute("SHOW DATABASES")
            return [row[1] for row in cur.fetchall()]
        finally:
            cur.close()

    def list_schemas(self, db: str) -> List[str]:
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        
        # Validate database name to prevent SQL injection
        self._validate_identifier(db, "database")
        
        cur = self._conn.cursor()
        try:
            cur.execute(f"SHOW SCHEMAS IN DATABASE {db}")  # SHOW statements require identifier, not parameter
            return [row[1] for row in cur.fetchall()]
        finally:
            cur.close()

    def list_roles(self) -> List[str]:
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        cur = self._conn.cursor()
        try:
            cur.execute("SHOW ROLES")
            return [row[1] for row in cur.fetchall()]
        finally:
            cur.close()

    def list_roles_detailed(self) -> List[Dict[str, Any]]:
        """List all roles with their detailed information."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        cur = self._conn.cursor()
        try:
            cur.execute("SHOW ROLES")
            columns = [desc[0] for desc in cur.description]
            roles = []
            for row in cur.fetchall():
                role_dict = dict(zip(columns, row))
                roles.append({
                    'created_on': role_dict.get('created_on', ''),
                    'name': role_dict.get('name', ''),
                    'is_default': role_dict.get('is_default', False),
                    'is_current': role_dict.get('is_current', False),
                    'is_inherited': role_dict.get('is_inherited', False),
                    'assigned_to_users': role_dict.get('assigned_to_users', 0),
                    'granted_to_roles': role_dict.get('granted_to_roles', 0),
                    'granted_roles': role_dict.get('granted_roles', 0),
                    'owner': role_dict.get('owner', ''),
                    'comment': role_dict.get('comment', '')
                })
            return roles
        finally:
            cur.close()

    def get_role_privileges(self, role_name: str) -> List[Dict[str, Any]]:
        """Get privileges granted to a specific role."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        
        # Validate role name to prevent SQL injection
        self._validate_identifier(role_name, "role")
        
        cur = self._conn.cursor()
        try:
            cur.execute(f"SHOW GRANTS TO ROLE {role_name}")  # SHOW statements require identifier, not parameter
            columns = [desc[0] for desc in cur.description]
            privileges = []
            for row in cur.fetchall():
                priv_dict = dict(zip(columns, row))
                privileges.append({
                    'created_on': priv_dict.get('created_on', ''),
                    'privilege': priv_dict.get('privilege', ''),
                    'granted_on': priv_dict.get('granted_on', ''),
                    'name': priv_dict.get('name', ''),
                    'granted_to': priv_dict.get('granted_to', ''),
                    'grantee_name': priv_dict.get('grantee_name', ''),
                    'grant_option': priv_dict.get('grant_option', False),
                    'granted_by': priv_dict.get('granted_by', '')
                })
            return privileges
        finally:
            cur.close()

    def get_role_grants(self, role_name: str) -> List[Dict[str, Any]]:
        """Get users and roles that have been granted a specific role."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        
        # Validate role name to prevent SQL injection
        self._validate_identifier(role_name, "role")
        
        cur = self._conn.cursor()
        try:
            cur.execute(f"SHOW GRANTS OF ROLE {role_name}")  # SHOW statements require identifier, not parameter
            columns = [desc[0] for desc in cur.description]
            grants = []
            for row in cur.fetchall():
                grant_dict = dict(zip(columns, row))
                grants.append({
                    'created_on': grant_dict.get('created_on', ''),
                    'role': grant_dict.get('role', ''),
                    'granted_to': grant_dict.get('granted_to', ''),
                    'grantee_name': grant_dict.get('grantee_name', ''),
                    'granted_by': grant_dict.get('granted_by', '')
                })
            return grants
        finally:
            cur.close()

    def list_warehouses(self) -> List[str]:
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        cur = self._conn.cursor()
        try:
            cur.execute("SHOW WAREHOUSES")
            return [row[0] for row in cur.fetchall()]
        finally:
            cur.close()

    def set_warehouse(self, warehouse: str) -> None:
        """Set the active warehouse for this session."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        
        # Validate warehouse name to prevent SQL injection
        self._validate_identifier(warehouse, "warehouse")
        
        self._warehouse = warehouse
        cur = self._conn.cursor()
        try:
            cur.execute(f"USE WAREHOUSE {warehouse}")  # USE statements require identifier, not parameter
        except Exception as e:
            # Re-raise warehouse errors as they are important for grants
            raise RuntimeError(f"Failed to set warehouse {warehouse}: {str(e)}")
        finally:
            cur.close()

    def list_stored_procedures(self, schema_name: str) -> List[str]:
        """List stored procedures in a given schema for debugging."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        cur = self._conn.cursor()
        try:
            cur.execute(f"SHOW PROCEDURES IN SCHEMA {schema_name}")
            return [row[1] for row in cur.fetchall()]  # Procedure name is usually in column 1
        except Exception as e:
            print(f"Error listing procedures in {schema_name}: {e}")
            return []
        finally:
            cur.close()

    def list_users(self) -> List[Dict[str, Any]]:
        """List all users with their details."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        cur = self._conn.cursor()
        try:
            cur.execute("SHOW USERS")
            columns = [desc[0] for desc in cur.description]
            users = []
            for row in cur.fetchall():
                user_dict = dict(zip(columns, row))
                users.append({
                    'name': user_dict.get('name', ''),
                    'login_name': user_dict.get('login_name', ''),
                    'display_name': user_dict.get('display_name', ''),
                    'first_name': user_dict.get('first_name', ''),
                    'last_name': user_dict.get('last_name', ''),
                    'email': user_dict.get('email', ''),
                    'disabled': user_dict.get('disabled', False),
                    'must_change_password': user_dict.get('must_change_password', False),
                    'snowflake_lock': user_dict.get('snowflake_lock', False),
                    'days_to_expiry': user_dict.get('days_to_expiry', ''),
                    'mins_to_unlock': user_dict.get('mins_to_unlock', ''),
                    'default_warehouse': user_dict.get('default_warehouse', ''),
                    'default_role': user_dict.get('default_role', ''),
                    'created_on': user_dict.get('created_on', ''),
                    'last_success_login': user_dict.get('last_success_login', ''),
                    'expires_at_time': user_dict.get('expires_at_time', ''),
                    'locked_until_time': user_dict.get('locked_until_time', ''),
                    # Security indicators
                    'has_rsa_public_key': user_dict.get('has_rsa_public_key', False),
                    'has_password': user_dict.get('has_password', False),
                    'has_mfa': user_dict.get('has_mfa', False)
                })
            return users
        finally:
            cur.close()

    # internal helper
    def _ensure_wh(self):
        if self._warehouse and self._conn is not None:
            cur = self._conn.cursor()
            try:
                # Warehouse name was already validated when set
                cur.execute(f"USE WAREHOUSE {self._warehouse}")  # USE statements require identifier, not parameter
            except Exception:
                # Ignore errors such as warehouse not found; caller may set another warehouse
                pass
            finally:
                cur.close()

    def get_user_details(self, username: str) -> Dict[str, Any]:
        """Get detailed information about a specific user from cache or view."""
        # Validate username to prevent SQL injection
        self._validate_identifier(username, "username")
        
        # Check if we have cached data for this user
        if username in self._users_cache:
            print(f"Retrieved user details for {username} from cache")
            return self._users_cache[username]
        
        # If not in cache, query the view for this specific user
        print(f"User {username} not in cache, querying view directly")
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        
        cur = self._conn.cursor()
        try:
            # Query the view for this specific user using parameterized query
            cur.execute("SELECT * FROM UPLAND_MAINTENANCE.SECURITY.V_USER_KEY_MANAGEMENT WHERE USERNAME = %s", (username,))
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()
            
            if not row:
                raise Exception(f"User {username} not found in view")
            
            user_dict = dict(zip(columns, row))
            
            # Calculate MFA status: positive value for HAS_MFA or EXT_AUTHN_DUO
            has_mfa_value = user_dict.get('HAS_MFA')
            ext_authn_duo_value = user_dict.get('EXT_AUTHN_DUO')
            
            # Check for positive values (any truthy value or positive number)
            has_mfa = False
            if has_mfa_value:
                if isinstance(has_mfa_value, (int, float)) and has_mfa_value > 0:
                    has_mfa = True
                elif isinstance(has_mfa_value, str) and has_mfa_value.lower() in ('true', '1', 'yes', 'y'):
                    has_mfa = True
                elif isinstance(has_mfa_value, bool) and has_mfa_value:
                    has_mfa = True
            
            if not has_mfa and ext_authn_duo_value:
                if isinstance(ext_authn_duo_value, (int, float)) and ext_authn_duo_value > 0:
                    has_mfa = True
                elif isinstance(ext_authn_duo_value, str) and ext_authn_duo_value.lower() in ('true', '1', 'yes', 'y'):
                    has_mfa = True
                elif isinstance(ext_authn_duo_value, bool) and ext_authn_duo_value:
                    has_mfa = True
            
            # Convert to the expected format
            user_details = {
                'user_id': user_dict.get('USER_ID', ''),
                'name': user_dict.get('USERNAME', username),
                'login_name': user_dict.get('LOGIN_NAME', ''),
                'display_name': user_dict.get('DISPLAY_NAME', ''),
                'first_name': user_dict.get('FIRST_NAME', ''),
                'last_name': user_dict.get('LAST_NAME', ''),
                'email': user_dict.get('EMAIL', ''),
                'disabled': self._convert_snowflake_boolean(user_dict.get('DISABLED')),
                'must_change_password': self._convert_snowflake_boolean(user_dict.get('MUST_CHANGE_PASSWORD')),
                'snowflake_lock': self._convert_snowflake_boolean(user_dict.get('SNOWFLAKE_LOCK')),
                'default_warehouse': user_dict.get('DEFAULT_WAREHOUSE', ''),
                'default_namespace': user_dict.get('DEFAULT_NAMESPACE', ''),
                'default_role': user_dict.get('DEFAULT_ROLE', ''),
                'default_secondary_role': user_dict.get('DEFAULT_SECONDARY_ROLE', ''),
                'created_on': user_dict.get('CREATED_ON', ''),
                'deleted_on': user_dict.get('DELETED_ON', ''),
                'last_success_login': user_dict.get('LAST_SUCCESS_LOGIN', ''),
                'expires_at': user_dict.get('EXPIRES_AT', ''),
                'locked_until_time': user_dict.get('LOCKED_UNTIL_TIME', ''),
                'password_last_set_time': user_dict.get('PASSWORD_LAST_SET_TIME', ''),
                'bypass_mfa_until': user_dict.get('BYPASS_MFA_UNTIL', ''),
                'has_password': self._convert_snowflake_boolean(user_dict.get('HAS_PASSWORD')),
                'has_mfa': has_mfa,
                'ext_authn_duo': user_dict.get('EXT_AUTHN_DUO', ''),
                'ext_authn_uid': user_dict.get('EXT_AUTHN_UID', ''),
                'has_rsa_public_key': self._convert_snowflake_boolean(user_dict.get('HAS_RSA_PUBLIC_KEY')),
                'comment': user_dict.get('COMMENT', ''),
                'owner': user_dict.get('OWNER', ''),
                'type': user_dict.get('TYPE', ''),
                'database_name': user_dict.get('DATABASE_NAME', ''),
                'database_id': user_dict.get('DATABASE_ID', ''),
                'schema_name': user_dict.get('SCHEMA_NAME', ''),
                'schema_id': user_dict.get('SCHEMA_ID', ''),
                # Note: View-only data, no fingerprints or key content available
                'rsa_public_key': None,
                'rsa_public_key_2': None,
                'rsa_public_key_fingerprint': '',
                'rsa_public_key_2_fingerprint': '',
                'view_only': True  # Flag to indicate this is view-only data
            }
            
            # Cache this user for future lookups
            self._users_cache[username] = user_details
            
            print(f"Retrieved and cached user details from view for {username}")
            return user_details
        finally:
            cur.close()

    def set_user_public_key(self, username: str, public_key: str, key_number: int = 1) -> Dict[str, Any]:
        """Set RSA public key for a user. key_number can be 1 or 2."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        
        # Validate username to prevent SQL injection
        self._validate_identifier(username, "username")
        
        if key_number not in [1, 2]:
            raise ValueError("key_number must be 1 or 2")
        
        # Extract just the key content (remove header/footer and join lines)
        lines = public_key.strip().split('\n')
        if len(lines) > 2 and lines[0].startswith('-----BEGIN') and lines[-1].startswith('-----END'):
            key_content = ''.join(lines[1:-1])
        else:
            # Assume it's already just the key content
            key_content = public_key.replace('\n', '')
        
        # Validate key content contains only base64 characters
        if not re.match(r'^[A-Za-z0-9+/=]*$', key_content):
            raise ValueError("Invalid public key format: contains non-base64 characters")
        
        cur = self._conn.cursor()
        try:
            if key_number == 1:
                cur.execute("ALTER USER %s SET RSA_PUBLIC_KEY=%s", (username, key_content))
            else:
                cur.execute("ALTER USER %s SET RSA_PUBLIC_KEY_2=%s", (username, key_content))
            
            return {
                'success': True,
                'message': f'RSA public key {key_number} set successfully for user {username}',
                'username': username,
                'key_number': key_number
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to set RSA public key for user {username}: {str(e)}',
                'username': username,
                'key_number': key_number
            }
        finally:
            cur.close()

    def unset_user_public_key(self, username: str, key_number: int = 1) -> Dict[str, Any]:
        """Remove RSA public key from a user. key_number can be 1 or 2."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        self._ensure_wh()
        
        # Validate username to prevent SQL injection
        self._validate_identifier(username, "username")
        
        if key_number not in [1, 2]:
            raise ValueError("key_number must be 1 or 2")
        
        cur = self._conn.cursor()
        try:
            if key_number == 1:
                cur.execute("ALTER USER %s UNSET RSA_PUBLIC_KEY", (username,))
            else:
                cur.execute("ALTER USER %s UNSET RSA_PUBLIC_KEY_2", (username,))
            
            return {
                'success': True,
                'message': f'RSA public key {key_number} removed successfully from user {username}',
                'username': username,
                'key_number': key_number
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to remove RSA public key from user {username}: {str(e)}',
                'username': username,
                'key_number': key_number
            }
        finally:
            cur.close()

    def update_user_rsa_key(self, username: str, public_key: str, unset_password: bool = False, new_type: str = None) -> Dict[str, Any]:
        """
        Enhanced RSA key update with stored procedure fallback to direct ALTER USER.
        Sets RSA_PUBLIC_KEY and optionally unsets password and/or changes user type.
        """
        # Validate username to prevent SQL injection
        self._validate_identifier(username, "username")
        
        # Extract just the key content (remove header/footer and join lines)
        lines = public_key.strip().split('\n')
        if len(lines) > 2 and lines[0].startswith('-----BEGIN') and lines[-1].startswith('-----END'):
            key_content = ''.join(lines[1:-1])
        else:
            # Assume it's already just the key content
            key_content = public_key.replace('\n', '')
        
        # Validate key content contains only base64 characters
        if not re.match(r'^[A-Za-z0-9+/=]*$', key_content):
            raise ValueError("Invalid public key format: contains non-base64 characters")
        
        # Validate new_type if provided
        if new_type and new_type.upper() not in ['PERSON', 'SERVICE', 'LEGACY_SERVICE', 'NULL']:
            raise ValueError("Invalid user type. Allowed: PERSON, SERVICE, LEGACY_SERVICE, NULL")
        
        # Try stored procedure first, fall back to direct ALTER USER
        try:
            # Use existing call_stored_procedure method for consistency
            result = self.call_stored_procedure(
                'UPLAND_MAINTENANCE.SECURITY.sp_update_user_rsa_key',
                [username, key_content, unset_password, new_type]
            )
            
            # Extract message from stored procedure result
            message = f'RSA key updated successfully for user {username}'
            if result.get('result') and len(result['result']) > 0:
                message = str(result['result'][0])
            elif result.get('rows') and len(result['rows']) > 0:
                message = str(result['rows'][0][0])
            
            return {
                'success': True,
                'message': message,
                'username': username,
                'actions_performed': {
                    'rsa_key_set': True,
                    'password_unset': unset_password,
                    'type_changed': bool(new_type and new_type.upper() != 'NULL')
                }
            }
        except Exception as stored_proc_error:
            print(f"Stored procedure failed, falling back to direct ALTER USER: {stored_proc_error}")
            
            # Fallback: use direct ALTER USER commands
            if self._conn is None:
                raise RuntimeError("Snowflake connection not initialised")
            self._ensure_wh()
            
            cur = self._conn.cursor()
            actions_performed = {
                'rsa_key_set': False,
                'password_unset': False,
                'type_changed': False
            }
            messages = []
            
            try:
                # Build SET clauses for ALTER USER
                set_clauses = []
                
                # Always set RSA public key
                set_clauses.append(f"RSA_PUBLIC_KEY = '{key_content}'")
                
                # Optionally unset password
                if unset_password:
                    set_clauses.append("PASSWORD = NULL")
                
                # Optionally change user type
                if new_type and new_type.upper() != 'NULL':
                    if new_type.upper() == 'NULL':
                        set_clauses.append("TYPE = NULL")
                    else:
                        set_clauses.append(f"TYPE = {new_type.upper()}")
                
                # Execute ALTER USER command
                alter_sql = f'ALTER USER "{username}" SET ' + ', '.join(set_clauses)
                print(f"Executing fallback ALTER USER: {alter_sql}")
                cur.execute(alter_sql)
                
                # Track successful actions
                actions_performed['rsa_key_set'] = True
                messages.append("RSA public key set successfully")
                
                if unset_password:
                    actions_performed['password_unset'] = True
                    messages.append("password unset (disabled password login)")
                
                if new_type and new_type.upper() != 'NULL':
                    actions_performed['type_changed'] = True
                    messages.append(f"user type changed to {new_type.upper()}")
                
                final_message = f"User {username} updated successfully: " + ", ".join(messages)
                
                return {
                    'success': True,
                    'message': final_message,
                    'username': username,
                    'actions_performed': actions_performed,
                    'fallback_used': True
                }
                
            except Exception as alter_error:
                return {
                    'success': False,
                    'message': f'Failed to update RSA key for user {username}: {str(alter_error)}',
                    'username': username,
                    'actions_performed': actions_performed,
                    'stored_proc_error': str(stored_proc_error),
                    'alter_user_error': str(alter_error)
                }
            finally:
                cur.close()

    def list_users_with_keys(self) -> List[Dict[str, Any]]:
        """List all users with enhanced key information for key management view."""
        users = self.list_users()
        
        # For each user, get detailed key information to ensure accurate filtering
        for user in users:
            try:
                details = self.get_user_details(user['name'])
                user['rsa_public_key_fingerprint'] = details.get('rsa_public_key_fingerprint', '')
                user['rsa_public_key_2_fingerprint'] = details.get('rsa_public_key_2_fingerprint', '')
                user['has_rsa_public_key_1'] = bool(details.get('rsa_public_key'))
                user['has_rsa_public_key_2'] = bool(details.get('rsa_public_key_2'))
                
                # Update the overall has_rsa_public_key flag based on detailed info
                user['has_rsa_public_key'] = user['has_rsa_public_key_1'] or user['has_rsa_public_key_2']
            except Exception as e:
                # If we can't get details, use conservative defaults
                print(f"Warning: Could not get key details for user {user['name']}: {e}")
                user['rsa_public_key_fingerprint'] = ''
                user['rsa_public_key_2_fingerprint'] = ''
                user['has_rsa_public_key_1'] = False
                user['has_rsa_public_key_2'] = False
                # Keep the original has_rsa_public_key value from SHOW USERS
        
        return users

    def _convert_snowflake_boolean(self, value) -> bool:
        """Convert Snowflake boolean values to proper Python boolean.
        
        Snowflake can return:
        - Python boolean: True/False
        - String: "true"/"false", "TRUE"/"FALSE", "1"/"0"
        - None/NULL values
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'y')
        # Handle numeric values
        return bool(value)

    def list_users_from_view(self) -> List[Dict[str, Any]]:
        """List all users from the V_USER_KEY_MANAGEMENT view for efficient key management."""
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        
        cur = self._conn.cursor()
        try:
            print("Starting list_users_from_view method...")
            
            # Check current context
            print("Checking current context...")
            try:
                cur.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_ROLE(), CURRENT_USER()")
                context = cur.fetchone()
                print(f"Current context - Database: {context[0]}, Schema: {context[1]}, Role: {context[2]}, User: {context[3]}")
            except Exception as context_error:
                print(f"Failed to get current context: {context_error}")
                raise
            
            # Find an available warehouse
            print("Finding available warehouses...")
            try:
                cur.execute("SHOW WAREHOUSES")
                warehouses = [row[0] for row in cur.fetchall()]
                print(f"Available warehouses: {warehouses}")
                
                if warehouses:
                    warehouse_to_use = warehouses[0]  # Use the first available warehouse
                    print(f"Using warehouse: {warehouse_to_use}")
                    # Validate warehouse name to prevent SQL injection
                    self._validate_identifier(warehouse_to_use, "warehouse")
                    cur.execute(f"USE WAREHOUSE {warehouse_to_use}")  # USE statements require identifier, not parameter
                    print(f"Successfully set warehouse to {warehouse_to_use}")
                else:
                    print("No warehouses available - trying without warehouse")
            except Exception as wh_error:
                print(f"Failed to set warehouse: {wh_error} - trying without warehouse")
            
            # Now try the view query with explicit database.schema.view reference
            print("Attempting to query V_USER_KEY_MANAGEMENT view...")
            try:
                cur.execute("SELECT * FROM UPLAND_MAINTENANCE.SECURITY.V_USER_KEY_MANAGEMENT")
                print(f"View query successful! Retrieved {cur.rowcount} rows")
            except Exception as view_error:
                print(f"Failed to query view: {view_error}")
                raise
            
            columns = [desc[0] for desc in cur.description]
            users = []
            
            for row in cur.fetchall():
                user_dict = dict(zip(columns, row))
                
                # Debug logging for first few users to see raw values
                if len(users) < 3:  # Log first 3 users
                    print(f"Debug - Raw Snowflake data for user {user_dict.get('USERNAME', 'unknown')}:")
                    print(f"  DISABLED: {user_dict.get('DISABLED')} (type: {type(user_dict.get('DISABLED'))})")
                    print(f"  MUST_CHANGE_PASSWORD: {user_dict.get('MUST_CHANGE_PASSWORD')} (type: {type(user_dict.get('MUST_CHANGE_PASSWORD'))})")
                    print(f"  SNOWFLAKE_LOCK: {user_dict.get('SNOWFLAKE_LOCK')} (type: {type(user_dict.get('SNOWFLAKE_LOCK'))})")
                    print(f"  HAS_MFA: {user_dict.get('HAS_MFA')} (type: {type(user_dict.get('HAS_MFA'))})")
                    print(f"  EXT_AUTHN_DUO: {user_dict.get('EXT_AUTHN_DUO')} (type: {type(user_dict.get('EXT_AUTHN_DUO'))})")
                
                # Calculate MFA status: positive value for HAS_MFA or EXT_AUTHN_DUO
                has_mfa_value = user_dict.get('HAS_MFA')
                ext_authn_duo_value = user_dict.get('EXT_AUTHN_DUO')
                
                # Check for positive values (any truthy value or positive number)
                has_mfa = False
                if has_mfa_value:
                    if isinstance(has_mfa_value, (int, float)) and has_mfa_value > 0:
                        has_mfa = True
                    elif isinstance(has_mfa_value, str) and has_mfa_value.lower() in ('true', '1', 'yes', 'y'):
                        has_mfa = True
                    elif isinstance(has_mfa_value, bool) and has_mfa_value:
                        has_mfa = True
                
                if not has_mfa and ext_authn_duo_value:
                    if isinstance(ext_authn_duo_value, (int, float)) and ext_authn_duo_value > 0:
                        has_mfa = True
                    elif isinstance(ext_authn_duo_value, str) and ext_authn_duo_value.lower() in ('true', '1', 'yes', 'y'):
                        has_mfa = True
                    elif isinstance(ext_authn_duo_value, bool) and ext_authn_duo_value:
                        has_mfa = True
                
                users.append({
                    'user_id': user_dict.get('USER_ID', ''),
                    'name': user_dict.get('USERNAME', ''),
                    'login_name': user_dict.get('LOGIN_NAME', ''),
                    'display_name': user_dict.get('DISPLAY_NAME', ''),
                    'first_name': user_dict.get('FIRST_NAME', ''),
                    'last_name': user_dict.get('LAST_NAME', ''),
                    'email': user_dict.get('EMAIL', ''),
                    'disabled': self._convert_snowflake_boolean(user_dict.get('DISABLED')),
                    'must_change_password': self._convert_snowflake_boolean(user_dict.get('MUST_CHANGE_PASSWORD')),
                    'snowflake_lock': self._convert_snowflake_boolean(user_dict.get('SNOWFLAKE_LOCK')),
                    'default_warehouse': user_dict.get('DEFAULT_WAREHOUSE', ''),
                    'default_namespace': user_dict.get('DEFAULT_NAMESPACE', ''),
                    'default_role': user_dict.get('DEFAULT_ROLE', ''),
                    'default_secondary_role': user_dict.get('DEFAULT_SECONDARY_ROLE', ''),
                    'created_on': user_dict.get('CREATED_ON', ''),
                    'deleted_on': user_dict.get('DELETED_ON', ''),
                    'last_success_login': user_dict.get('LAST_SUCCESS_LOGIN', ''),
                    'expires_at': user_dict.get('EXPIRES_AT', ''),
                    'locked_until_time': user_dict.get('LOCKED_UNTIL_TIME', ''),
                    'password_last_set_time': user_dict.get('PASSWORD_LAST_SET_TIME', ''),
                    'bypass_mfa_until': user_dict.get('BYPASS_MFA_UNTIL', ''),
                    'has_password': self._convert_snowflake_boolean(user_dict.get('HAS_PASSWORD')),
                    'has_mfa': has_mfa,
                    'ext_authn_duo': user_dict.get('EXT_AUTHN_DUO', ''),
                    'ext_authn_uid': user_dict.get('EXT_AUTHN_UID', ''),
                    'has_rsa_public_key': self._convert_snowflake_boolean(user_dict.get('HAS_RSA_PUBLIC_KEY')),
                    'comment': user_dict.get('COMMENT', ''),
                    'owner': user_dict.get('OWNER', ''),
                    'type': user_dict.get('TYPE', ''),
                    'database_name': user_dict.get('DATABASE_NAME', ''),
                    'database_id': user_dict.get('DATABASE_ID', ''),
                    'schema_name': user_dict.get('SCHEMA_NAME', ''),
                    'schema_id': user_dict.get('SCHEMA_ID', ''),
                    # Remove individual key flags since we only use HAS_RSA_PUBLIC_KEY now
                    'has_rsa_public_key_1': False,
                    'has_rsa_public_key_2': False,
                    'rsa_public_key_fingerprint': '',
                    'rsa_public_key_2_fingerprint': ''
                })
            
            print(f"Successfully loaded {len(users)} users from view")
            return users
        finally:
            cur.close()

    def list_users_with_keys_optimized(self) -> List[Dict[str, Any]]:
        """Optimized method that calls the view only once and caches all user data."""
        # Get all users from the view in a single call
        users = self.list_users_from_view()
        print(f"Single view call loaded {len(users)} users - no additional queries needed")
        
        # Cache all user data by username for efficient individual lookups
        self._users_cache = {}
        for user in users:
            self._users_cache[user['name']] = user
        self._cache_timestamp = time.time()
        
        print(f"Cached {len(self._users_cache)} users for efficient individual lookups")
        
        # All data is now available from the view, no need for individual user calls
        # The view provides all the information we need for the key management interface
        
        return users

    def clear_users_cache(self) -> None:
        """Clear the cached user data to force a fresh load from the view."""
        self._users_cache = {}
        self._cache_timestamp = None
        print("User cache cleared")


# Module-level singleton for convenience
client = SnowflakeClient() 