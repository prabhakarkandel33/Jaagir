"""Throttle classes shared by the services.

``ScopedRateThrottle`` would need a ``throttle_scope`` per view; a dedicated
subclass is clearer and lets us keep the tighter "auth" rate in one place.
"""

from __future__ import annotations

from rest_framework.throttling import ScopedRateThrottle


class AuthRateThrottle(ScopedRateThrottle):
    """Applies ``REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['auth']``."""

    scope = "auth"
