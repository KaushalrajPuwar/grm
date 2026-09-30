"""Live session pointers in Redis. Payloads stay in SQLite."""


# TODO: get/set session state with TTL, redacted logs.
class SessionStore:
    def get(self, session_id):
        raise NotImplementedError

    def set(self, session_id, state):
        raise NotImplementedError
