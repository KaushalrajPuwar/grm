"""Per session blob snapshots in a SQLite file. Postgres path stays open."""


# TODO: save_blob/fetch_blob keyed by session with fetched_at and cleanup.
class SnapshotStore:
    def save_blob(self, session_id, blob):
        raise NotImplementedError

    def fetch_blob(self, session_id):
        raise NotImplementedError
