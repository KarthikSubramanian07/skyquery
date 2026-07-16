"""Tests for the on-disk cache and its stable keying."""

from __future__ import annotations

from skyquery.core.cache import DiskCache, cache_key


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class TestCacheKey:
    def test_param_order_does_not_matter(self) -> None:
        a = cache_key("simbad", "q", {"name": "Vega", "radius": 1})
        b = cache_key("simbad", "q", {"radius": 1, "name": "Vega"})
        assert a == b

    def test_none_and_missing_collide(self) -> None:
        a = cache_key("simbad", "q", {"name": "Vega", "extra": None})
        b = cache_key("simbad", "q", {"name": "Vega"})
        assert a == b

    def test_different_source_differs(self) -> None:
        a = cache_key("simbad", "q", {"name": "Vega"})
        b = cache_key("ned", "q", {"name": "Vega"})
        assert a != b


class TestDiskCache:
    def test_set_then_get(self, tmp_path) -> None:
        cache = DiskCache(tmp_path)
        cache.set("k1", {"hello": "world"})
        assert cache.get("k1") == {"hello": "world"}

    def test_miss_returns_none(self, tmp_path) -> None:
        assert DiskCache(tmp_path).get("nope") is None

    def test_ttl_expiry(self, tmp_path) -> None:
        clock = FakeClock()
        cache = DiskCache(tmp_path, ttl_seconds=10.0, clock=clock)
        cache.set("k", "value")
        assert cache.get("k") == "value"
        clock.t += 11.0
        assert cache.get("k") is None

    def test_get_or_set_computes_once(self, tmp_path) -> None:
        cache = DiskCache(tmp_path)
        calls = {"n": 0}

        def producer() -> str:
            calls["n"] += 1
            return "computed"

        v1, cached1 = cache.get_or_set("k", producer)
        v2, cached2 = cache.get_or_set("k", producer)
        assert v1 == v2 == "computed"
        assert cached1 is False
        assert cached2 is True
        assert calls["n"] == 1

    def test_clear(self, tmp_path) -> None:
        cache = DiskCache(tmp_path)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.clear() == 2
        assert cache.get("a") is None
