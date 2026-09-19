import asyncio
import time


class RateLimiter:
    __slots__ = ('_interval', '_lock', '_next_at')

    def __init__(self, requests_per_second: float = 1.0) -> None:
        if requests_per_second <= 0:
            raise ValueError('requests_per_second must be positive')
        self._interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_at = time.monotonic() + self._interval
