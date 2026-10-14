"""Rate limiting that survives a Redis outage.

DRF's ``ScopedRateThrottle`` keeps its counters in the shared cache (Redis). If Redis is unreachable
it raises, and every throttled view (login, register, password reset, email verification…) answers
HTTP 500: nobody can log in or recover an account until Redis is back. Here, connection trouble
pauses rate limiting instead (and is logged); real mistakes such as a scope with no configured rate
are still errors.

While Redis is down the limits are NOT enforced. The per-code attempt limit on password-reset and
verification codes lives in the database, so that protection stays on.
"""
import logging

from redis.exceptions import RedisError
from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger(__name__)

# What a broken cache connection looks like: redis-py's errors, or the socket errors under them.
CACHE_ERRORS = (RedisError, OSError)


class FailOpenScopedRateThrottle(ScopedRateThrottle):
    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except CACHE_ERRORS as exc:
            logger.warning(
                "Rate limiting is unavailable, allowing the request (scope=%s, error=%s)",
                getattr(view, "throttle_scope", None),
                type(exc).__name__,
            )
            return True
