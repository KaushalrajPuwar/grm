"""Agent roles. Each role is bound to exactly one model at construction.

`base.py` holds the adapter and the shared model invocation. The three roles are
thin: a role name, a constitution, and a node function. They live in the harness
routing layer rather than here, because a role is a binding, not a module.
"""
