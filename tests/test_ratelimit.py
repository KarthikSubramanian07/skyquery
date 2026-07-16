"""Tests for the rate-limiter and backoff (good-citizenship, a hard floor).

These prove SkyQuery throttles bursts and backs off, so a free public service is
never hammered. The clock and sleep are injected, so the tests are deterministic
and never actually sleep.
"""

from __future__ import annotations

import pytest

from skyquery.core.ratelimit import BackoffPolicy, RateLimiter, retry_with_backoff


class FakeClock:
    """A controllable monotonic clock plus a sleep that advances it."""

    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class TestRateLimiter:
    def test_min_interval_spacing_is_enforced(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(
            max_calls=1000, period=1.0, min_interval=0.2, clock=clock.now, sleep=clock.sleep
        )
        limiter.acquire()  # first call: no wait
        limiter.acquire()  # must wait min_interval
        assert clock.sleeps
        assert clock.sleeps[-1] == pytest.approx(0.2)

    def test_window_limit_blocks_burst(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(
            max_calls=3, period=1.0, min_interval=0.0, clock=clock.now, sleep=clock.sleep
        )
        for _ in range(3):
            limiter.acquire()
        assert clock.sleeps == []  # first three fit in the window
        limiter.acquire()  # fourth must wait for the window to slide
        assert clock.sleeps
        assert clock.sleeps[-1] > 0

    def test_calls_spread_out_do_not_wait(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(
            max_calls=2, period=1.0, min_interval=0.1, clock=clock.now, sleep=clock.sleep
        )
        limiter.acquire()
        clock.t += 5.0  # plenty of time passes
        limiter.acquire()
        assert clock.sleeps == []


class TestBackoff:
    def test_delays_grow_exponentially(self) -> None:
        policy = BackoffPolicy(base=0.5, factor=2.0, max_delay=30.0, max_attempts=5)
        assert policy.delay_for(1) == 0.5
        assert policy.delay_for(2) == 1.0
        assert policy.delay_for(3) == 2.0
        assert policy.delay_for(4) == 4.0

    def test_delay_is_capped(self) -> None:
        policy = BackoffPolicy(base=1.0, factor=10.0, max_delay=5.0)
        assert policy.delay_for(10) == 5.0

    def test_retry_succeeds_after_transient_failures(self) -> None:
        clock = FakeClock()
        policy = BackoffPolicy(base=0.1, max_attempts=5)
        attempts = {"n": 0}

        def flaky() -> str:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise TimeoutError("transient")
            return "ok"

        result = retry_with_backoff(
            flaky, policy=policy, retryable=lambda e: True, sleep=clock.sleep
        )
        assert result == "ok"
        assert attempts["n"] == 3
        assert len(clock.sleeps) == 2  # slept before the 2 retries

    def test_non_retryable_raises_immediately(self) -> None:
        policy = BackoffPolicy(max_attempts=5)

        def bad() -> None:
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            retry_with_backoff(bad, policy=policy, retryable=lambda e: False, sleep=lambda s: None)

    def test_gives_up_after_max_attempts(self) -> None:
        policy = BackoffPolicy(base=0.01, max_attempts=3)
        attempts = {"n": 0}

        def always_fail() -> None:
            attempts["n"] += 1
            raise TimeoutError("nope")

        with pytest.raises(TimeoutError):
            retry_with_backoff(
                always_fail, policy=policy, retryable=lambda e: True, sleep=lambda s: None
            )
        assert attempts["n"] == 3
