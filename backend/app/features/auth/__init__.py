"""Auth & RBAC feature: login, current-user, RBAC models + seed."""
# Router is imported directly in main.py — no eager import here to avoid
# circular imports (deps.py → auth.models → auth.__init__ → auth.router → deps.py).
