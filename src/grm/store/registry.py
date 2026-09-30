"""In-process session registry.

Interface boundary, so the Redis-backed store can replace this without the flow
code noticing. Holds an AuthSession per transport session id.

Demo only. The map is unbounded and does not survive a restart. Production must
put TTL and persistence behind this same interface.
"""

from __future__ import annotations

from threading import Lock

from grm.auth.gate import AuthSession, begin_session


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, AuthSession] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> AuthSession:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = begin_session()
            return self._sessions[session_id]

    def reset(self, session_id: str) -> AuthSession:
        """Drop verification and the snapshot together, never apart."""
        with self._lock:
            fresh = begin_session()
            self._sessions[session_id] = fresh
            return fresh

    def drop(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        return len(self._sessions)
