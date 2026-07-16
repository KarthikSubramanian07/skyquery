"""The local SQLite query and citation log.

Every query SkyQuery runs and every source it touches is recorded here so a
session can be reproduced and cited later. All SQL is parameterized. The
database lives on your machine and nowhere else.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from skyquery.models.provenance import Provenance

_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    source      TEXT NOT NULL,
    operation   TEXT NOT NULL,
    query       TEXT NOT NULL,
    url         TEXT,
    cached      INTEGER NOT NULL DEFAULT 0,
    citation    TEXT
);
CREATE INDEX IF NOT EXISTS idx_query_log_source ON query_log(source);
CREATE INDEX IF NOT EXISTS idx_query_log_ts ON query_log(ts);
"""


@dataclass
class QueryRecord:
    """One row of the query log."""

    ts: str
    source: str
    operation: str
    query: str
    url: str | None
    cached: bool
    citation: str | None


class QueryStore:
    """A thin, parameterized wrapper over the SQLite query/citation log."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record(self, provenance: Provenance, operation: str) -> None:
        """Append a provenance record to the log."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO query_log (ts, source, operation, query, url, cached, citation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    provenance.retrieved_at or "",
                    provenance.source,
                    operation,
                    provenance.query,
                    provenance.url,
                    1 if provenance.cached else 0,
                    provenance.citation,
                ),
            )

    def recent(self, limit: int = 50) -> list[QueryRecord]:
        """Return the most recent query records, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, source, operation, query, url, cached, citation "
                "FROM query_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            QueryRecord(
                ts=r["ts"],
                source=r["source"],
                operation=r["operation"],
                query=r["query"],
                url=r["url"],
                cached=bool(r["cached"]),
                citation=r["citation"],
            )
            for r in rows
        ]

    def sources_used(self) -> list[str]:
        """Return the distinct sources touched, sorted."""
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT source FROM query_log ORDER BY source").fetchall()
        return [r["source"] for r in rows]

    def clear(self) -> None:
        """Delete every log row."""
        with self._connect() as conn:
            conn.execute("DELETE FROM query_log")
