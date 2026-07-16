"""Virtual Observatory TAP allowlisting and ADQL request hardening.

``VoTapSource`` is an escape hatch for services SkyQuery does not wrap natively.
Callers can pass any TAP URL, which is classic SSRF if left unchecked. We only
permit HTTPS endpoints on a known-good host list, and we refuse ADQL that is not
a single SELECT or that tries to bypass our row cap.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from skyquery.errors import ValidationError

# Hostnames of well-known public TAP services. Subdomains of these registrable
# suffixes are accepted only when the full hostname is listed here.
ALLOWED_TAP_HOSTS: frozenset[str] = frozenset(
    {
        "gea.esac.esa.int",
        "hipparcos-tools.cosmos.esa.int",
        "simbad.cds.unistra.fr",
        "vizier.cds.unistra.fr",
        "tapvizier.cds.unistra.fr",
        "irsa.ipac.caltech.edu",
        "vao.stsci.edu",
        "mast.stsci.edu",
        "archive.eso.org",
        "www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca",
        "ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca",
        "dc.g-vo.org",
        "dc.zah.uni-heidelberg.de",
        "gaia.ari.uni-heidelberg.de",
        "vo.astron.nl",
        "sky.esa.int",
        "casda.csiro.au",
        "datalab.noirlab.edu",
        "www.cosmos.esa.int",
    }
)

_SELECT_RE = re.compile(r"^\s*select\b", re.IGNORECASE)
_HAS_TOP_RE = re.compile(r"^\s*select\s+top\s+\d+\b", re.IGNORECASE)


def validate_tap_url(tap_url: object) -> str:
    """Return a cleaned TAP URL or raise :class:`ValidationError`."""
    if not isinstance(tap_url, str) or not tap_url.strip():
        raise ValidationError("tap_url must be a non-empty string")
    parsed = urlparse(tap_url.strip())
    if parsed.scheme.lower() != "https":
        raise ValidationError("tap_url must use https")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValidationError("tap_url is missing a hostname")
    # Block literal IPs (private or public) — only named public VO hosts.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValidationError("tap_url must use a hostname, not an IP address")
    if host not in ALLOWED_TAP_HOSTS:
        raise ValidationError(
            f"tap host {host!r} is not on the SkyQuery allowlist; "
            "use a first-class adapter or file an issue to add a public TAP service"
        )
    if parsed.username or parsed.password:
        raise ValidationError("tap_url must not include credentials")
    return parsed.geturl()


def prepare_adql(adql: object, *, row_limit: int) -> str:
    """Validate ADQL and ensure a ``TOP N`` cap is present."""
    if not isinstance(adql, str) or not adql.strip():
        raise ValidationError("adql must be a non-empty string")
    text = adql.strip()
    if ";" in text:
        raise ValidationError("adql must be a single statement")
    if not _SELECT_RE.match(text):
        raise ValidationError("adql must be a SELECT query")
    if row_limit < 1 or row_limit > 500:
        raise ValidationError("row_limit must be between 1 and 500")
    if _HAS_TOP_RE.match(text):
        return text
    # Case-insensitive SELECT → SELECT TOP N
    return _SELECT_RE.sub(f"SELECT TOP {row_limit} ", text, count=1)
