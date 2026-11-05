"""Agent roles. Each role is bound to exactly one model at construction.

`base.py` holds the adapter and the shared model invocation. Roles are thin: a
name, a constitution, and a binding to one model. The harness decides which role
answers. In single-agent mode only the `single` role is used.
"""
