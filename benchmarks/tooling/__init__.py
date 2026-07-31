"""Registry-driven Harbor suite tooling.

This package contains the control-plane modules that validate, render, and
regenerate Jacobian's committed Harbor datasets. It is intentionally
importable without the optional ``harbor`` runtime: only digest computation
imports Harbor, and it does so lazily so registry, manifest, topology,
visibility, verifier-support, and job-rendering checks run in the normal test
environment.
"""
