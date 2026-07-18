"""Small, dependency-free guards for the public outfit endpoint."""

from collections import deque
from time import monotonic

from fastapi import Request

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def client_ip(request: Request) -> str:
    """Return Vercel's forwarded client address, with a safe local fallback."""

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else "unknown"


class SlidingWindowLimiter:
    """Best-effort in-process limiter for costly live pipeline requests.

    The Vercel deployment may run multiple instances, so this is a deliberate
    first boundary rather than a distributed quota system.
    """

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = {}

    def allow(self, key: str, maximum: int, window_seconds: float = 60) -> bool:
        """Record a request if it fits within the caller's sliding window."""

        now = monotonic()
        requests = self._requests.get(key)
        if requests is None:
            requests = deque()
            self._requests[key] = requests
        while requests and now - requests[0] >= window_seconds:
            requests.popleft()
        if len(requests) >= maximum:
            return False
        requests.append(now)
        return True
