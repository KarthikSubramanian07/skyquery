"""SkyQuery: the sky, queryable.

A local, open-source MCP server and CLI that puts the working astronomer's
toolkit behind one conversation. Object lookups, catalog cross-matches,
ephemerides, literature, and observation planning, all normalized with
provenance you can cite. Runs entirely on your machine.

SkyQuery is an independent project and is not affiliated with, or endorsed by,
NASA, JPL, CDS/Strasbourg, STScI, ESA, the Astropy project, or any other service
it wraps.
"""

from __future__ import annotations

__version__ = "0.1.0"

from skyquery.client import SkyQuery

__all__ = ["SkyQuery", "__version__"]
