"""Build the shipped replay fixtures from recorded real service data.

Run once (or after refreshing captures) to regenerate ``src/skyquery/_fixtures``.
The Horizons, SBDB, SIMBAD, and Gaia payloads are derived from real recorded
responses; the ADS/arXiv/NASA samples are small representative snapshots clearly
marked as such. Everything is written under the exact ``cache_key`` filename the
adapters look up, so the offline demo and the test suite resolve deterministically.

Usage:
    python scripts/make_fixtures.py [path/to/capture_dir]
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from skyquery.core.cache import cache_key  # noqa: E402

FIXTURES_DIR = ROOT / "src" / "skyquery" / "_fixtures"

# Columns kept from the Horizons ephemeris CSV, mapped to the adapter's raw keys.
_HORIZONS_KEYS = ["datetime_str", "RA", "DEC", "delta", "delta_rate", "V", "elong", "alpha", "airmass"]


def _write(source: str, operation: str, params: dict[str, Any], payload: Any) -> None:
    key = cache_key(source, operation, params)
    name = f"{source}__{operation}__{key[:16]}.json"
    path = FIXTURES_DIR / name
    path.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    print(f"wrote {name}  <-  {source}.{operation} {params}")


def _num(value: str) -> float | None:
    try:
        f = float(value)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def build_horizons(cap: Path) -> None:
    csv_path = cap / "horizons_apophis_2029.csv"
    rows: list[dict[str, Any]] = []
    with csv_path.open() as fh:
        for record in csv.DictReader(fh):
            row: dict[str, Any] = {}
            for key in _HORIZONS_KEYS:
                if key in record:
                    row[key] = record[key] if key == "datetime_str" else _num(record[key])
            rows.append(row)
    payload = {"target": "99942 Apophis", "location": "500@399", "rows": rows}
    params = {
        "target": "99942 Apophis",
        "location": "500@399",
        "start": "2029-04-13",
        "stop": "2029-04-14",
        "step": "1h",
    }
    _write("horizons", "ephemerides", params, payload)


def build_sbdb(cap: Path) -> None:
    data = json.loads((cap / "sbdb_apophis.json").read_text())
    obj = data["object"]
    phys = data["phys_par"]
    elem = data["orbit"]["elements"]

    def unit_val(v: Any) -> float | None:
        if v is None:
            return None
        return _num(str(v).split()[0])

    payload = {
        "fullname": obj["fullname"],
        "neo": bool(obj.get("neo")),
        "pha": bool(obj.get("pha")),
        "orbit_class": obj.get("orbit_class", {}).get("name"),
        "diameter": unit_val(phys.get("diameter")),
        "H": phys.get("H"),
        "albedo": phys.get("albedo"),
        "rot_per": unit_val(phys.get("rot_per")),
        "orbit": {
            "e": elem.get("e"),
            "a": unit_val(elem.get("a")),
            "q": unit_val(elem.get("q")),
            "i": unit_val(elem.get("i")),
            "per": unit_val(elem.get("per")),
        },
    }
    _write("sbdb", "query", {"target": "Apophis"}, payload)


def build_simbad(cap: Path) -> None:
    objects = {
        "Vega": {
            "main_id": "* alf Lyr",
            "ra": 279.234734787025,
            "dec": 38.783688956244,
            "otype": "dS*",
            "sp_type": "A0V",
            "plx_value": 130.23,
            "pmra": 200.94,
            "pmdec": 286.23,
            "rvz_radvel": -13.5,
            "rvz_redshift": -4.503013899492814e-05,
            "flux": {"V": 0.029999999329447746},
            "ids": ["* alf Lyr", "NAME Vega", "HD 172167", "HR 7001", "HIP 91262"],
        },
        "M31": {
            "main_id": "M  31",
            "ra": 10.684708333333333,
            "dec": 41.268750000000004,
            "otype": "AGN",
            "sp_type": None,
            "plx_value": None,
            "pmra": None,
            "pmdec": None,
            "rvz_radvel": -300.0,
            "rvz_redshift": -0.0010001920937326991,
            "flux": {"V": 3.440000057220459},
            "ids": ["M  31", "NAME Andromeda", "NGC  224", "2C 56"],
        },
        "Betelgeuse": {
            "main_id": "* alf Ori",
            "ra": 88.79293899,
            "dec": 7.407063999,
            "otype": "s*r",
            "sp_type": "M1-M2Ia-Iab",
            "plx_value": 4.51,
            "pmra": 26.42,
            "pmdec": 9.6,
            "rvz_radvel": 21.91,
            "rvz_redshift": 7.3e-05,
            "flux": {"V": 0.42},
            "ids": ["* alf Ori", "NAME Betelgeuse", "HD 39801", "HR 2061", "HIP 27989"],
        },
    }
    for name, payload in objects.items():
        _write("simbad", "query_object", {"name": name}, payload)


def build_gaia(cap: Path) -> None:
    csv_path = cap / "gaia_vega_cone.csv"
    units = {
        "source_id": "",
        "ra": "deg",
        "dec": "deg",
        "parallax": "mas",
        "pmra": "mas / yr",
        "pmdec": "mas / yr",
        "phot_g_mean_mag": "mag",
        "bp_rp": "mag",
    }
    rows: list[dict[str, Any]] = []
    with csv_path.open() as fh:
        for record in csv.DictReader(fh):
            rows.append(
                {
                    "source_id": int(record["source_id"]),
                    "ra": _num(record["ra"]),
                    "dec": _num(record["dec"]),
                    "parallax": _num(record["parallax"]),
                    "pmra": _num(record["pmra"]),
                    "pmdec": _num(record["pmdec"]),
                    "phot_g_mean_mag": _num(record["phot_g_mean_mag"]),
                    "bp_rp": _num(record["bp_rp"]),
                }
            )
    payload = {"columns": units, "rows": rows}
    params = {"ra": 279.234735, "dec": 38.783689, "radius": 0.02, "row_limit": 20}
    _write("gaia", "cone_search", params, payload)


def build_literature() -> None:
    # Representative snapshot samples (arXiv is a live search; a fixture is a snapshot).
    apophis_arxiv = {
        "entries": [
            {
                "id": "2404.01234",
                "title": "Radar and Optical Observations of Near-Earth Asteroid 99942 Apophis",
                "summary": (
                    "We report updated physical and orbital characterization of the "
                    "potentially hazardous asteroid 99942 Apophis ahead of its 2029 "
                    "close approach to Earth."
                ),
                "authors": ["A. Researcher", "B. Observer", "C. Collaborator"],
                "year": 2024,
            }
        ]
    }
    _write("arxiv", "search", {"q": "Apophis", "max_results": 1}, apophis_arxiv)
    _write("arxiv", "search", {"q": "Apophis", "max_results": 5}, apophis_arxiv)

    vega_arxiv = {
        "entries": [
            {
                "id": "2312.05678",
                "title": "The Debris Disk of Vega Revisited",
                "summary": "New infrared photometry constrains the structure of Vega's debris disk.",
                "authors": ["D. Astronomer", "E. Coauthor"],
                "year": 2023,
            }
        ]
    }
    _write("arxiv", "search", {"q": 'object:"Vega"', "max_results": 3}, vega_arxiv)


def build_nasa() -> None:
    apod = {
        "date": "2026-07-15",
        "title": "A Spiral Galaxy in Ursa Major",
        "explanation": (
            "This is a representative offline sample of NASA's Astronomy Picture of "
            "the Day, shipped so the demo runs without a network connection."
        ),
        "url": "https://apod.nasa.gov/apod/image/sample.jpg",
        "media_type": "image",
        "copyright": None,
    }
    _write("nasa", "apod", {"date": None}, apod)


def main() -> None:
    cap = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if cap is None or not cap.exists():
        print("usage: python scripts/make_fixtures.py <capture_dir>", file=sys.stderr)
        print("(capture_dir must contain the recorded CSV/JSON captures)", file=sys.stderr)
        raise SystemExit(2)
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    build_horizons(cap)
    build_sbdb(cap)
    build_simbad(cap)
    build_gaia(cap)
    build_literature()
    build_nasa()
    print(f"\nfixtures written to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
