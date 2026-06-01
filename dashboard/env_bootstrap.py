"""Load environment variables before app.config is imported."""

from app.env_bootstrap import bootstrap_env

__all__ = ["bootstrap_env"]
