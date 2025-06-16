"""snowflake_client.py

Thin wrapper around the Snowflake Python connector.
Phase-0: skeleton only, with no real execution logic.  Later phases will
implement connection pooling and stored-procedure execution helpers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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
                cur.execute(f"USE WAREHOUSE {warehouse}")
            except Exception:
                # Ignore errors such as warehouse not found; caller may set another warehouse
                pass
            finally:
                cur.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

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
        cur = self._conn.cursor()
        try:
            cur.execute(f"SHOW SCHEMAS IN DATABASE {db}")
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
        
        self._warehouse = warehouse
        cur = self._conn.cursor()
        try:
            cur.execute(f"USE WAREHOUSE {warehouse}")
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
                cur.execute(f"USE WAREHOUSE {self._warehouse}")
            except Exception:
                # Ignore errors such as warehouse not found; caller may set another warehouse
                pass
            finally:
                cur.close()


# Module-level singleton for convenience
client = SnowflakeClient() 