"""Session and snapshot storage.

`registry.py` holds the in-process session map used by the demo. The
Redis-backed store and the snapshot store described in ARCHITECTURE.md are
deployment targets that land behind this same interface.
"""
