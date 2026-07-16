"""High-level composed operations.

These functions orchestrate one or more adapters and the deterministic core into
the operations the MCP tools and the CLI expose. They are the single place where
"resolve a name, then get its ephemeris, then find papers" is expressed, so both
surfaces behave identically.
"""

from __future__ import annotations

from skyquery.services.operations import (
    ApophisReport,
    ObjectDossier,
    apophis_report,
    cone_search,
    crossmatch_targets,
    ephemeris,
    literature,
    object_dossier,
    observability,
    resolve_object,
    small_body,
)

__all__ = [
    "ApophisReport",
    "ObjectDossier",
    "apophis_report",
    "cone_search",
    "crossmatch_targets",
    "ephemeris",
    "literature",
    "object_dossier",
    "observability",
    "resolve_object",
    "small_body",
]
