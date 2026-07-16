"""SkyQuery exception hierarchy.

Errors are typed so the CLI can print something sane, the MCP server can return
a clean tool error, and the retry logic can tell a transient network failure
from a bad request. Error messages must never contain credentials.
"""

from __future__ import annotations


class SkyQueryError(Exception):
    """Base class for every SkyQuery error."""


class ConfigError(SkyQueryError):
    """Configuration or setup is missing or invalid."""


class CredentialError(SkyQueryError):
    """A required credential is missing. Never carries the credential value."""


class SourceError(SkyQueryError):
    """A data source failed to answer or answered with something unusable."""


class TransientSourceError(SourceError):
    """A retryable failure from a data source (timeout, 5xx, rate limit)."""


class NotFoundError(SourceError):
    """The requested object, catalog, or record does not exist."""


class ReplayError(SkyQueryError):
    """No recorded fixture matched a request while running in replay mode."""


class ValidationError(SkyQueryError):
    """User-supplied input failed validation before any network call."""
