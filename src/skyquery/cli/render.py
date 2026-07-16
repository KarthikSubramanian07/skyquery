"""Rich rendering helpers for the CLI.

Clean, aligned, colorblind-safe output that degrades gracefully when stdout is
not a TTY or when NO_COLOR is set. Numbers are always shown with their units and,
for positions, their reference frame.
"""

from __future__ import annotations

import os

from rich.console import Console
from rich.table import Table

from skyquery.models.catalog import CatalogTable
from skyquery.models.ephemeris import Ephemeris
from skyquery.models.object import Object
from skyquery.models.paper import Paper
from skyquery.models.quantity import Measurement


def make_console() -> Console:
    """Build a console that respects NO_COLOR and non-TTY output."""
    no_color = bool(os.environ.get("NO_COLOR"))
    return Console(no_color=no_color, highlight=False, soft_wrap=False)


def _m(value: Measurement | None) -> str:
    return str(value) if value is not None else "-"


def render_object(console: Console, obj: Object) -> None:
    table = Table(title=f"[bold]{obj.name}[/bold]", show_header=False, box=None, pad_edge=False)
    table.add_column("field", style="dim")
    table.add_column("value")
    table.add_row("type", obj.object_type or "-")
    if obj.position is not None:
        table.add_row("position", str(obj.position))
        table.add_row("RA (hms)", obj.position.ra_hms)
        table.add_row("Dec (dms)", obj.position.dec_dms)
    table.add_row("parallax", _m(obj.parallax))
    table.add_row("pm RA", _m(obj.proper_motion_ra))
    table.add_row("pm Dec", _m(obj.proper_motion_dec))
    table.add_row("radial velocity", _m(obj.radial_velocity))
    table.add_row("redshift", _m(obj.redshift))
    table.add_row("spectral type", obj.spectral_type or "-")
    if obj.photometry:
        mags = "  ".join(f"{p.band}={_m(p.magnitude)}" for p in obj.photometry)
        table.add_row("photometry", mags)
    console.print(table)
    _print_source(console, obj.provenance.service)


def render_ephemeris(console: Console, eph: Ephemeris, *, limit: int = 12) -> None:
    table = Table(title=f"[bold]{eph.target}[/bold]  observer={eph.observer}")
    table.add_column("epoch (UT)")
    table.add_column("RA [ICRS]", justify="right")
    table.add_column("Dec [ICRS]", justify="right")
    table.add_column("delta", justify="right")
    table.add_column("V", justify="right")
    for row in eph.rows[:limit]:
        table.add_row(
            row.epoch_utc,
            f"{row.position.lon:.5f}",
            f"{row.position.lat:+.5f}",
            _m(row.delta),
            _m(row.v_magnitude),
        )
    if len(eph.rows) > limit:
        table.caption = f"showing {limit} of {len(eph.rows)} rows"
    console.print(table)
    _print_source(console, eph.provenance.service)


def render_catalog(console: Console, cat: CatalogTable, *, limit: int = 15) -> None:
    table = Table(title=f"[bold]{cat.catalog}[/bold]  ({cat.row_count} rows)")
    for col in cat.columns:
        header = f"{col.name}" + (f"\n[dim]{col.unit}[/dim]" if col.unit else "")
        table.add_column(header, justify="right")
    for row in cat.rows[:limit]:
        table.add_row(*[_fmt(row.get(c.name)) for c in cat.columns])
    console.print(table)
    _print_source(console, cat.provenance.service)


def render_papers(console: Console, papers: list[Paper]) -> None:
    if not papers:
        console.print("[dim]no papers found[/dim]")
        return
    for i, paper in enumerate(papers, 1):
        author = paper.first_author or "?"
        year = paper.year or "----"
        console.print(f"[bold]{i}.[/bold] {paper.title}")
        console.print(f"   [dim]{author} et al. ({year})[/dim]  {paper.url or ''}")
    _print_source(console, papers[0].provenance.service)


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _print_source(console: Console, service: str) -> None:
    console.print(f"[dim]source: {service}[/dim]")
