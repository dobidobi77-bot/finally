"""Database-layer errors. `str(e)` on either is safe to show the user."""

from __future__ import annotations


class InsufficientFunds(Exception):  # noqa: N818 - name frozen in INTERFACES.md
    """Raised when a buy costs more than the available cash balance."""


class InsufficientShares(Exception):  # noqa: N818 - name frozen in INTERFACES.md
    """Raised when a sell exceeds the quantity currently held."""
