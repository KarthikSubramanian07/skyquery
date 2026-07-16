"""SkyQuery's deterministic core.

Everything that must be correct lives here and nowhere else: unit, frame, and
epoch conversion; positional cross-match; citation assembly; the rate-limiter;
and the on-disk cache. None of it touches the network, so all of it is directly
and hermetically testable.
"""

from __future__ import annotations

from skyquery.core.cache import DiskCache, cache_key
from skyquery.core.citations import (
    acknowledgment_for,
    assemble_citations,
    render_citations_block,
)
from skyquery.core.convert import (
    angular_separation,
    convert_unit,
    parallax_to_distance,
    propagate_proper_motion,
    to_altaz,
    transform_frame,
)
from skyquery.core.crossmatch import CrossMatch, CrossMatchResult, cross_match
from skyquery.core.ratelimit import BackoffPolicy, RateLimiter, retry_with_backoff

__all__ = [
    "BackoffPolicy",
    "CrossMatch",
    "CrossMatchResult",
    "DiskCache",
    "RateLimiter",
    "acknowledgment_for",
    "angular_separation",
    "assemble_citations",
    "cache_key",
    "convert_unit",
    "cross_match",
    "parallax_to_distance",
    "propagate_proper_motion",
    "render_citations_block",
    "retry_with_backoff",
    "to_altaz",
    "transform_frame",
]
