"""Rate limiting and exponential backoff.

These are free, publicly funded academic services. SkyQuery throttles every
external call to human scale and backs off on failure. This is enforced in code,
not left to good intentions, so the throttle is a hard floor rather than a
preference. The clock is injectable so tests are deterministic and never sleep.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """A sliding-window rate limiter with a minimum spacing between calls.

    Two independent floors are enforced:

    * ``min_interval`` seconds must elapse between any two consecutive calls.
    * At most ``max_calls`` may start within any ``period`` second window.

    Args:
        max_calls: Maximum number of calls allowed per ``period``.
        period: The sliding window length in seconds.
        min_interval: Minimum spacing between two consecutive calls, in seconds.
        clock: Monotonic time source, injectable for tests.
        sleep: Sleep function, injectable for tests.
    """

    max_calls: int = 5
    period: float = 1.0
    min_interval: float = 0.1
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _calls: deque[float] = field(default_factory=deque, init=False, repr=False)
    _last: float | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def acquire(self) -> float:
        """Block until a call is permitted. Returns the seconds spent waiting."""
        waited = 0.0
        while True:
            with self._lock:
                now = self.clock()
                wait = self._required_wait(now)
                if wait <= 0:
                    self._record(now)
                    return waited
            self.sleep(wait)
            waited += wait

    def _required_wait(self, now: float) -> float:
        # Drop calls that have aged out of the window.
        while self._calls and now - self._calls[0] >= self.period:
            self._calls.popleft()
        spacing_wait = 0.0
        if self._last is not None:
            spacing_wait = max(0.0, self.min_interval - (now - self._last))
        window_wait = 0.0
        if len(self._calls) >= self.max_calls:
            window_wait = self.period - (now - self._calls[0])
        return max(spacing_wait, window_wait)

    def _record(self, now: float) -> None:
        self._calls.append(now)
        self._last = now


@dataclass
class BackoffPolicy:
    """Exponential backoff with a capped delay.

    ``delay_for(attempt)`` returns the delay before retry ``attempt`` (1-indexed).
    Deterministic (no jitter) so tests can assert exact sequences.
    """

    base: float = 0.5
    factor: float = 2.0
    max_delay: float = 30.0
    max_attempts: int = 5

    def delay_for(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        return min(self.max_delay, self.base * (self.factor ** (attempt - 1)))

    def should_retry(self, attempt: int) -> bool:
        return attempt < self.max_attempts


def retry_with_backoff(
    fn: Callable[[], object],
    *,
    policy: BackoffPolicy,
    retryable: Callable[[Exception], bool],
    sleep: Callable[[float], None] = time.sleep,
) -> object:
    """Call ``fn``, retrying on retryable exceptions with exponential backoff.

    Raises the last exception if all attempts are exhausted or the error is not
    retryable.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as exc:
            if not retryable(exc) or not policy.should_retry(attempt):
                raise
            sleep(policy.delay_for(attempt))
