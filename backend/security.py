"""security.py – session and inactivity helpers (Phase-0 stub)."""

from __future__ import annotations

import time

INACTIVITY_TIMEOUT_SECONDS = 15 * 60  # 15 minutes


class InactivityTimer:
    """Tracks last-activity timestamp and signals expiry."""

    def __init__(self, timeout: int = INACTIVITY_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout
        self._last_activity: float = time.time()

    def reset(self) -> None:
        self._last_activity = time.time()

    def expired(self) -> bool:
        return (time.time() - self._last_activity) > self.timeout


# Placeholder for PAT validation – will integrate with Snowflake OAuth later.

def validate_pat(pat: str) -> bool:  # noqa: D401
    """Return *True* if the given PAT looks syntactically valid.

    Phase-0: simple length check (>=20 chars); real validation will involve
    hitting Snowflake's token introspection endpoint or a quick auth query.
    """
    return bool(pat) and len(pat) >= 20  # arbitrary minimal check 