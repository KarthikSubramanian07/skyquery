"""Citation assembly.

A session touches several services. Each one asks to be acknowledged a specific
way. This module deduplicates the provenance seen during a session into a clean,
ready-to-paste citations block. Reproducibility is the default, not a mode.
"""

from __future__ import annotations

from collections.abc import Iterable

from skyquery.models.provenance import Citation, Provenance

# The acknowledgment text each wrapped service asks users to include. These are
# paraphrased pointers to each service's own acknowledgment policy, not a claim
# of affiliation. The authoritative wording always lives with the service.
SERVICE_ACKNOWLEDGMENTS: dict[str, tuple[str, str]] = {
    "simbad": (
        "SIMBAD (CDS, Strasbourg)",
        "This research has made use of the SIMBAD database, operated at CDS, "
        "Strasbourg, France (Wenger et al. 2000, A&AS 143, 9).",
    ),
    "ned": (
        "NASA/IPAC Extragalactic Database (NED)",
        "This research has made use of the NASA/IPAC Extragalactic Database (NED), "
        "funded by NASA and operated by Caltech.",
    ),
    "vizier": (
        "VizieR (CDS, Strasbourg)",
        "This research has made use of the VizieR catalogue access tool, CDS, "
        "Strasbourg, France (DOI: 10.26093/cds/vizier).",
    ),
    "gaia": (
        "ESA Gaia mission / DPAC",
        "This work has made use of data from the European Space Agency (ESA) "
        "mission Gaia, processed by the Gaia Data Processing and Analysis "
        "Consortium (DPAC).",
    ),
    "sdss": (
        "Sloan Digital Sky Survey (SDSS)",
        "Funding for the Sloan Digital Sky Survey has been provided by the Alfred "
        "P. Sloan Foundation and participating institutions.",
    ),
    "twomass": (
        "2MASS (UMass / IPAC-Caltech)",
        "This publication makes use of data products from the Two Micron All Sky "
        "Survey, a joint project of UMass and IPAC/Caltech, funded by NASA and NSF.",
    ),
    "wise": (
        "WISE (UCLA / JPL-Caltech)",
        "This publication makes use of data products from the Wide-field Infrared "
        "Survey Explorer, a joint project of UCLA and JPL/Caltech, funded by NASA.",
    ),
    "panstarrs": (
        "Pan-STARRS1 Surveys",
        "The Pan-STARRS1 Surveys have been made possible through contributions by "
        "the Institute for Astronomy, University of Hawaii, and its partners.",
    ),
    "horizons": (
        "JPL Horizons (NASA/JPL-Caltech)",
        "Ephemerides were obtained from the JPL Horizons system, "
        "Jet Propulsion Laboratory, Caltech.",
    ),
    "sbdb": (
        "JPL Small-Body Database (NASA/JPL-Caltech)",
        "Small-body data were obtained from the JPL Small-Body Database, "
        "Jet Propulsion Laboratory, Caltech.",
    ),
    "ads": (
        "NASA Astrophysics Data System (ADS)",
        "This research has made use of NASA's Astrophysics Data System Bibliographic Services.",
    ),
    "arxiv": (
        "arXiv.org",
        "This research has made use of the arXiv e-print repository, "
        "operated by Cornell University.",
    ),
    "mast": (
        "Barbara A. Mikulski Archive for Space Telescopes (MAST)",
        "Some of the data presented in this work were obtained from the Mikulski "
        "Archive for Space Telescopes (MAST) at STScI.",
    ),
    "nasa": (
        "NASA Open APIs",
        "This product uses NASA's Open APIs (api.nasa.gov). "
        "Not affiliated with or endorsed by NASA.",
    ),
    "astropy": (
        "Astropy",
        "This research made use of Astropy, a community-developed core Python "
        "package for astronomy (Astropy Collaboration).",
    ),
    "astroquery": (
        "astroquery",
        "This research made use of astroquery (Ginsburg et al. 2019, AJ, 157, 98).",
    ),
    "astroplan": (
        "astroplan",
        "This research made use of astroplan, an open-source observation-planning "
        "package for Astropy.",
    ),
    "vo": (
        "Virtual Observatory service",
        "This research made use of a Virtual Observatory service accessed via a "
        "standard IVOA protocol.",
    ),
}


def acknowledgment_for(source: str) -> tuple[str, str] | None:
    """Return the ``(service_name, citation_text)`` for a source id, if known."""
    return SERVICE_ACKNOWLEDGMENTS.get(source.lower())


def assemble_citations(provenances: Iterable[Provenance]) -> list[Citation]:
    """Deduplicate a stream of provenance into one citation per distinct source.

    References (bibcodes, URLs) seen for a source are collected and sorted so the
    output is deterministic regardless of query order.
    """
    by_source: dict[str, Citation] = {}
    refs: dict[str, set[str]] = {}
    for prov in provenances:
        key = prov.source.lower()
        if key not in by_source:
            ack = acknowledgment_for(key)
            service = ack[0] if ack else prov.service
            text = ack[1] if ack else (prov.citation or prov.service)
            by_source[key] = Citation(source=key, service=service, text=text, references=[])
            refs[key] = set()
        if prov.url:
            refs[key].add(prov.url)
    return [
        by_source[k].model_copy(update={"references": sorted(refs[k])}) for k in sorted(by_source)
    ]


def render_citations_block(citations: list[Citation]) -> str:
    """Render citations as a plain-text acknowledgments block."""
    if not citations:
        return "No sources were queried in this session."
    lines = ["Acknowledgments", "=" * 15, ""]
    for cite in citations:
        lines.append(f"- {cite.text}")
        for ref in cite.references:
            lines.append(f"    {ref}")
    lines.append("")
    lines.append(
        "SkyQuery is an independent open-source tool and is not affiliated with, "
        "or endorsed by, any of the services above."
    )
    return "\n".join(lines)
