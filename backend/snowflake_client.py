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
        cur = self._conn.cursor()
        try:
            result = cur.callproc(proc_name, args)
            return {"success": True, "result": result}
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Metadata fetch helpers
    # ------------------------------------------------------------------
    def list_databases(self) -> List[str]:
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        cur = self._conn.cursor()
        try:
            cur.execute("SHOW DATABASES")
            return [row[1] for row in cur.fetchall()]
        finally:
            cur.close()

    def list_schemas(self, db: str) -> List[str]:
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        cur = self._conn.cursor()
        try:
            cur.execute(f"SHOW SCHEMAS IN DATABASE {db}")
            return [row[1] for row in cur.fetchall()]
        finally:
            cur.close()

    def list_roles(self) -> List[str]:
        if self._conn is None:
            raise RuntimeError("Snowflake connection not initialised")
        cur = self._conn.cursor()
        try:
            cur.execute("SHOW ROLES")
            return [row[1] for row in cur.fetchall()]
        finally:
            cur.close()


# Module-level singleton for convenience
client = SnowflakeClient() 