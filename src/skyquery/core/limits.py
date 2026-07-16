"""Input clamps for catalog, literature, and ephemeris requests.

SkyQuery talks to free public astronomy services. Unbounded tool arguments can
exhaust local memory and burn upstream quotas in a single call, even with the
rate limiter spacing requests. These helpers are the hard ceilings shared by the
MCP tools, the CLI, and the service layer.
"""

from __future__ import annotations

import re
from datetime import datetime

from skyquery.errors import ValidationError

MAX_ROW_LIMIT = 100
MAX_LITERATURE_ROWS = 50
MAX_RADIUS_DEG = 5.0
MAX_CROSSMATCH_TARGETS = 50
MAX_EPHEMERIS_POINTS = 2000
MAX_NAME_LEN = 256
MAX_QUERY_LEN = 2000

_STEP_RE = re.compile(r"^(\d+(?:\.\d+)?)([smhd])$", re.IGNORECASE)
_DATE_FMTS = ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")


def clamp_row_limit(row_limit: object, *, ceiling: int = MAX_ROW_LIMIT) -> int:
    """Return a positive row limit no larger than ``ceiling``."""
    if isinstance(row_limit, bool) or not isinstance(row_limit, int):
        raise ValidationError("row_limit must be an integer")
    if row_limit < 1:
        raise ValidationError("row_limit must be >= 1")
    return min(row_limit, ceiling)


def clamp_radius_deg(radius_deg: object, *, ceiling: float = MAX_RADIUS_DEG) -> float:
    """Return a positive cone radius no larger than ``ceiling`` degrees."""
    try:
        value = float(radius_deg)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValidationError("radius_deg must be a number") from exc
    if value <= 0:
        raise ValidationError("radius_deg must be > 0")
    if value > ceiling:
        raise ValidationError(f"radius_deg must be <= {ceiling}")
    return value


def clamp_literature_rows(rows: object) -> int:
    return clamp_row_limit(rows, ceiling=MAX_LITERATURE_ROWS)


def clamp_targets(targets: object) -> list[str]:
    if not isinstance(targets, list):
        raise ValidationError("targets must be a list of strings")
    if len(targets) > MAX_CROSSMATCH_TARGETS:
        raise ValidationError(f"at most {MAX_CROSSMATCH_TARGETS} cross-match targets allowed")
    cleaned: list[str] = []
    for name in targets:
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("cross-match targets must be non-empty strings")
        if len(name) > MAX_NAME_LEN:
            raise ValidationError(f"target name exceeds {MAX_NAME_LEN} characters")
        cleaned.append(name.strip())
    return cleaned


def clamp_query_text(query: object, *, what: str = "query") -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValidationError(f"{what} must be a non-empty string")
    if len(query) > MAX_QUERY_LEN:
        raise ValidationError(f"{what} exceeds {MAX_QUERY_LEN} characters")
    return query.strip()


def _parse_epoch(raw: str) -> datetime:
    text = raw.strip()
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValidationError(f"unrecognized epoch {raw!r}; use YYYY-MM-DD or YYYY-MM-DD HH:MM")


def _step_seconds(step: str) -> float:
    match = _STEP_RE.fullmatch(step.strip())
    if not match:
        raise ValidationError(f"unsupported ephemeris step {step!r}; use forms like 1h, 30m, 10d")
    amount = float(match.group(1))
    if amount <= 0:
        raise ValidationError("ephemeris step must be positive")
    unit = match.group(2).lower()
    multipliers = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
    return amount * multipliers[unit]


def validate_ephemeris_window(start: str, stop: str, step: str) -> None:
    """Reject ephemeris requests that would request an absurd number of points."""
    start_dt = _parse_epoch(start)
    stop_dt = _parse_epoch(stop)
    if stop_dt <= start_dt:
        raise ValidationError("ephemeris stop must be after start")
    span = (stop_dt - start_dt).total_seconds()
    step_s = _step_seconds(step)
    points = int(span / step_s) + 1
    if points > MAX_EPHEMERIS_POINTS:
        raise ValidationError(
            f"ephemeris would request ~{points} points "
            f"(max {MAX_EPHEMERIS_POINTS}); widen the step or shorten the window"
        )
