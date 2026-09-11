"""Service-layer errors."""

from __future__ import annotations


class ServiceError(Exception):
    """str(e) is the human-readable message put into {"error": ...} with 400."""
