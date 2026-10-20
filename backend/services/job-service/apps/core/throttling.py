"""Throttle classes shared by the services.

``ScopedRateThrottle`` would need a ``throttle_scope`` per view; a dedicated
subclass is clearer and lets us keep the tighter "auth" rate in one place.
"""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class AuthRateThrottle(SimpleRateThrottle):
    """Applies ``REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['auth']``.

    It subclasses ``SimpleRateThrottle``, not ``ScopedRateThrottle``: the
    scoped class reads ``view.throttle_scope`` and returns True when the view
    does not define it, which silently disabled this throttle.
    """

    scope = "auth"

    def get_cache_key(self, request, view):
        ident = request.user.pk if request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
