"""Agent & Tool management feature: DB-driven agents/tools that replace the
constants in `features/agent/settings.py`."""
# Router is imported directly in main.py — no eager import here to avoid
# circular imports (deps.py → auth.models → ...).
