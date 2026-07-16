"""The `skyquery` command-line interface.

A clean, scriptable front door to the same operations the MCP server exposes.
Every command takes ``--json`` for machine output and ``--live`` to leave replay
mode and hit the real services. With no flags it runs against the shipped
fixtures, so a fresh install answers the Apophis demo offline.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from skyquery import __version__, services
from skyquery.auth import CREDENTIAL_KEYS, credential_status, delete_credential, set_credential
from skyquery.cli import render
from skyquery.client import SkyQuery
from skyquery.config import Settings
from skyquery.core.convert import convert_unit, transform_frame
from skyquery.errors import SkyQueryError
from skyquery.models.coordinates import SkyPosition
from skyquery.models.quantity import Measurement
from skyquery.store.db import QueryStore

app = typer.Typer(
    name="skyquery",
    help="The sky, queryable. Real astronomy data, one command.",
    no_args_is_help=True,
    add_completion=False,
)

console = render.make_console()


class _State:
    json_out: bool = False
    live: bool = False


state = _State()


def _client() -> SkyQuery:
    settings = Settings.from_env()
    if state.live:
        settings = settings.model_copy(update={"replay": False})
    store: QueryStore | None = None
    if not settings.replay:
        settings.ensure_dirs()
        store = QueryStore(settings.db_path)
    return SkyQuery(settings, store=store)


def _emit(model: object) -> None:
    if state.json_out:
        if hasattr(model, "model_dump"):
            console.print_json(json.dumps(model.model_dump()))  # type: ignore[attr-defined]
        else:
            console.print_json(json.dumps(model, default=str))


@app.callback()
def _root(  # pyright: ignore[reportUnusedFunction] - Typer callback invoked via decorator
    json_out: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    live: Annotated[
        bool, typer.Option("--live", help="Leave replay mode; query live services.")
    ] = False,
) -> None:
    state.json_out = json_out
    state.live = live


@app.command()
def version() -> None:
    """Print the SkyQuery version."""
    console.print(f"SkyQuery {__version__}")


@app.command()
def resolve(name: Annotated[str, typer.Argument(help="Object name or identifier.")]) -> None:
    """Resolve an object name to coordinates and measured properties."""
    obj = services.resolve_object(_client(), name)
    if state.json_out:
        _emit(obj)
    else:
        render.render_object(console, obj)


@app.command()
def ephemeris(
    target: Annotated[str, typer.Argument(help="Solar-system body, e.g. '99942 Apophis'.")],
    start: Annotated[str, typer.Option(help="UT start, YYYY-MM-DD.")] = "2029-04-13",
    stop: Annotated[str, typer.Option(help="UT stop, YYYY-MM-DD.")] = "2029-04-14",
    step: Annotated[str, typer.Option(help="Sampling step, e.g. 1h.")] = "1h",
    location: Annotated[str, typer.Option(help="Horizons observer code.")] = "500@399",
) -> None:
    """Compute a JPL Horizons ephemeris for a solar-system body."""
    eph = services.ephemeris(
        _client(), target, start=start, stop=stop, step=step, location=location
    )
    if state.json_out:
        _emit(eph)
    else:
        render.render_ephemeris(console, eph)


@app.command("small-body")
def small_body(
    designation: Annotated[str, typer.Argument(help="Asteroid/comet designation.")],
) -> None:
    """Look up an asteroid or comet's physical and orbital parameters."""
    body = services.small_body(_client(), designation)
    if state.json_out:
        _emit(body)
    else:
        console.print(f"[bold]{body.fullname}[/bold]")
        console.print(f"  diameter: {body.diameter or '-'}   H: {body.absolute_magnitude or '-'}")
        console.print(f"  albedo: {body.albedo or '-'}   rotation: {body.rotation_period or '-'}")
        console.print(
            f"  a: {body.semi_major_axis or '-'}   e: {body.eccentricity or '-'}   "
            f"i: {body.inclination or '-'}"
        )
        console.print(f"[dim]source: {body.provenance.service}[/dim]")


@app.command()
def cone(
    center: Annotated[str, typer.Argument(help="Object name or 'RA DEC' in degrees.")],
    radius: Annotated[float, typer.Option(help="Radius in degrees.")] = 0.05,
    catalog: Annotated[str, typer.Option(help="'gaia' or a VizieR catalog id.")] = "gaia",
    rows: Annotated[int, typer.Option(help="Maximum rows.")] = 15,
) -> None:
    """Cone search a catalog around a position."""
    parts = center.replace(",", " ").split()
    target: str | tuple[float, float]
    if len(parts) == 2:
        try:
            target = (float(parts[0]), float(parts[1]))
        except ValueError:
            target = center
    else:
        target = center
    cat = services.cone_search(_client(), target, radius, catalog=catalog, row_limit=rows)
    if state.json_out:
        _emit(cat)
    else:
        render.render_catalog(console, cat)


@app.command()
def literature(
    query: Annotated[str, typer.Argument(help="Search query.")],
    rows: Annotated[int, typer.Option(help="Max results.")] = 5,
    prefer: Annotated[str, typer.Option(help="'ads' or 'arxiv'.")] = "arxiv",
) -> None:
    """Search the astronomy literature (ADS or arXiv)."""
    papers = services.literature(_client(), query, prefer=prefer, rows=rows)
    if state.json_out:
        _emit({"papers": [p.model_dump() for p in papers]})
    else:
        render.render_papers(console, papers)


@app.command()
def convert(
    value: Annotated[float, typer.Argument(help="Numeric value.")],
    from_unit: Annotated[str, typer.Argument(help="Source unit, e.g. 'pc'.")],
    to_unit: Annotated[str, typer.Argument(help="Target unit, e.g. 'lyr'.")],
) -> None:
    """Convert a value between units with astropy's tested conversions."""
    result = convert_unit(Measurement(value=value, unit=from_unit), to_unit)
    if state.json_out:
        _emit(result)
    else:
        console.print(f"{value} {from_unit} = [bold]{result}[/bold]")


@app.command()
def frame(
    ra: Annotated[float, typer.Argument(help="RA in degrees.")],
    dec: Annotated[float, typer.Argument(help="Dec in degrees.")],
    to: Annotated[str, typer.Option(help="Target frame.")] = "galactic",
    src: Annotated[str, typer.Option("--from", help="Source frame.")] = "icrs",
) -> None:
    """Transform coordinates between reference frames."""
    result = transform_frame(SkyPosition(lon=ra, lat=dec, frame=src), to)  # type: ignore[arg-type]
    if state.json_out:
        _emit(result)
    else:
        console.print(str(result))


@app.command()
def demo() -> None:
    """Run the headline Apophis demo: size, 2029 close approach, and a paper."""
    report = services.apophis_report(_client(), with_paper=True)
    if state.json_out:
        _emit(report)
        return
    console.print(f"[bold]{report.body.fullname}[/bold]")
    console.print(
        f"  size: {report.body.diameter or 'unknown'}   H: {report.body.absolute_magnitude or '-'}"
    )
    lunar = report.closest_distance_lunar.value or 0.0
    console.print(
        f"  closest approach: [bold]{report.closest_epoch}[/bold]  "
        f"{report.closest_distance_au}  ({lunar:.3f} lunar distances)"
    )
    if report.v_magnitude:
        console.print(f"  visual magnitude at approach: {report.v_magnitude}")
    if report.latest_paper:
        console.print(
            f"  paper: {report.latest_paper.title} ({report.latest_paper.year or '----'})"
        )
    console.print()
    console.print(f"[italic]{report.narrative}[/italic]")


@app.command()
def apod(date: Annotated[str | None, typer.Option(help="UTC date YYYY-MM-DD.")] = None) -> None:
    """Fetch NASA's Astronomy Picture of the Day."""
    picture = _client().nasa.apod(date)
    if state.json_out:
        _emit(picture)
    else:
        console.print(f"[bold]{picture.title}[/bold] ({picture.date})")
        console.print(picture.explanation)
        if picture.url:
            console.print(f"[dim]{picture.url}[/dim]")


@app.command()
def setup() -> None:
    """Create the local cache, log, and config directories. Idempotent."""
    settings = Settings.from_env()
    settings.ensure_dirs()
    QueryStore(settings.db_path)
    console.print(f"SkyQuery home: [bold]{settings.home}[/bold]")
    console.print(f"  cache:     {settings.cache_dir}")
    console.print(f"  downloads: {settings.downloads_dir}")
    console.print(f"  database:  {settings.db_path}")
    console.print("[green]Ready.[/green] Run `skyquery demo` to try it offline.")


@app.command()
def login(
    service: Annotated[str, typer.Argument(help=f"One of: {', '.join(CREDENTIAL_KEYS)}.")],
) -> None:
    """Store a free API key in your OS keychain (never a file)."""
    if service not in CREDENTIAL_KEYS:
        console.print(
            f"[red]Unknown service {service!r}.[/red] Known: {', '.join(CREDENTIAL_KEYS)}"
        )
        raise typer.Exit(1)
    token = typer.prompt(f"{service} token", hide_input=True)
    set_credential(service, token)
    console.print(f"[green]Stored {service} token in the OS keychain.[/green]")


@app.command()
def logout(service: Annotated[str, typer.Argument(help="Service to forget.")]) -> None:
    """Remove a stored API key from your OS keychain."""
    delete_credential(service)
    console.print(f"[green]Removed {service} token (if it was present).[/green]")


@app.command()
def status() -> None:
    """Show configuration and which optional keys are set."""
    settings = Settings.from_env()
    console.print(f"SkyQuery {__version__}")
    console.print(f"  mode: {'replay (offline)' if settings.replay else 'live'}")
    console.print(f"  home: {settings.home}")
    console.print("  credentials:")
    for name, present in credential_status().items():
        mark = "[green]set[/green]" if present else "[dim]not set[/dim]"
        console.print(f"    {name}: {mark}")


@app.command()
def cite() -> None:
    """Print acknowledgments for a demo session (shows the citation format)."""
    client = _client()
    services.apophis_report(client, with_paper=True)
    console.print(client.citations_block())


def _run() -> None:
    try:
        app()
    except SkyQueryError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(1) from exc


if __name__ == "__main__":  # pragma: no cover
    _run()
