"""Credential access via the OS keychain.

Optional free API keys (ADS, NASA) are read from and written to the operating
system keychain through ``keyring``. They never touch a plaintext file, never
enter the repository, and never appear in a log line or an MCP payload. An
environment-variable fallback exists for advanced users and CI, and is the only
path that does not use the keychain, kept deliberately explicit.
"""

from __future__ import annotations

import contextlib
import os

from skyquery.config import CREDENTIAL_KEYS
from skyquery.errors import CredentialError

_SERVICE = "skyquery"

# Environment fallbacks, checked only when the keychain has nothing.
_ENV_FALLBACK: dict[str, str] = {
    "ads": "ADS_DEV_KEY",
    "nasa": "NASA_API_KEY",
}


def _keyring():
    import keyring

    return keyring


def set_credential(name: str, value: str) -> None:
    """Store a credential in the OS keychain. Never writes to disk."""
    _validate_name(name)
    if not value or not value.strip():
        raise CredentialError(f"refusing to store an empty {name} credential")
    _keyring().set_password(_SERVICE, name, value.strip())


def get_credential(name: str) -> str | None:
    """Return a credential from the keychain, or the env fallback, or ``None``.

    The returned value is never logged. Callers must treat it as opaque.
    """
    _validate_name(name)
    try:
        value = _keyring().get_password(_SERVICE, name)
    except Exception:
        value = None
    if value:
        return value
    env_name = _ENV_FALLBACK.get(name)
    if env_name:
        return os.environ.get(env_name)
    return None


def delete_credential(name: str) -> None:
    """Remove a credential from the keychain if present."""
    _validate_name(name)
    with contextlib.suppress(Exception):  # deleting a missing key is a no-op
        _keyring().delete_password(_SERVICE, name)


def require_credential(name: str) -> str:
    """Return a credential or raise a :class:`CredentialError` naming only the key."""
    value = get_credential(name)
    if not value:
        raise CredentialError(
            f"no {name} credential found. Run `skyquery login` to add one, "
            f"or set the {_ENV_FALLBACK.get(name, name.upper())} environment variable."
        )
    return value


def credential_status() -> dict[str, bool]:
    """Return which known credentials are configured, without revealing values."""
    return {name: get_credential(name) is not None for name in CREDENTIAL_KEYS}


def _validate_name(name: str) -> None:
    if name not in CREDENTIAL_KEYS:
        raise CredentialError(
            f"unknown credential {name!r}; known credentials: {', '.join(CREDENTIAL_KEYS)}"
        )
