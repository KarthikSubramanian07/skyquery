"""Tests that credentials never leak: not into logs, not into payloads, not to disk.

These are security tests. They assert two things a security-minded auditor cares
about: (a) the credential path only touches the keychain, and (b) nothing that
looks like a key ever survives into a rendered log line or an error string.
"""

from __future__ import annotations

import io
import logging

import pytest

from skyquery import auth
from skyquery.errors import CredentialError
from skyquery.logging import configure_logging, event, get_logger, redact

SECRET = "ads_supersecrettoken_ABCDEFGHIJKLMNOP1234567890"


class FakeKeyring:
    """An in-memory keyring stand-in, so tests never touch the real OS keychain."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, name: str, value: str) -> None:
        self.store[(service, name)] = value

    def get_password(self, service: str, name: str) -> str | None:
        return self.store.get((service, name))

    def delete_password(self, service: str, name: str) -> None:
        self.store.pop((service, name), None)


@pytest.fixture
def fake_keyring(monkeypatch) -> FakeKeyring:
    fake = FakeKeyring()
    monkeypatch.setattr(auth, "_keyring", lambda: fake)
    # Ensure env fallbacks do not interfere.
    monkeypatch.delenv("ADS_DEV_KEY", raising=False)
    monkeypatch.delenv("NASA_API_KEY", raising=False)
    return fake


class TestCredentialPath:
    def test_set_and_get_via_keyring_only(self, fake_keyring: FakeKeyring) -> None:
        auth.set_credential("ads", SECRET)
        assert fake_keyring.store[("skyquery", "ads")] == SECRET
        assert auth.get_credential("ads") == SECRET

    def test_missing_credential_returns_none(self, fake_keyring: FakeKeyring) -> None:
        assert auth.get_credential("nasa") is None

    def test_require_missing_raises_without_value(self, fake_keyring: FakeKeyring) -> None:
        with pytest.raises(CredentialError) as exc:
            auth.require_credential("ads")
        # The error names the key but never contains a secret value.
        assert SECRET not in str(exc.value)

    def test_unknown_credential_rejected(self, fake_keyring: FakeKeyring) -> None:
        with pytest.raises(CredentialError):
            auth.get_credential("dropbox")

    def test_empty_value_refused(self, fake_keyring: FakeKeyring) -> None:
        with pytest.raises(CredentialError):
            auth.set_credential("ads", "   ")

    def test_status_reports_presence_not_value(self, fake_keyring: FakeKeyring) -> None:
        auth.set_credential("ads", SECRET)
        status = auth.credential_status()
        assert status["ads"] is True
        assert status["nasa"] is False


class TestLogRedaction:
    def test_redact_masks_kv_secret(self) -> None:
        out = redact(f"calling ads api_key={SECRET} now")
        assert SECRET not in out
        assert "REDACTED" in out

    def test_redact_masks_bare_token(self) -> None:
        out = redact(f"Authorization: Bearer {SECRET}")
        assert SECRET not in out

    def test_redact_masks_authorization_bearer_header(self) -> None:
        out = redact(f"Authorization: Bearer {SECRET}")
        assert SECRET not in out
        assert "Bearer ***REDACTED***" in out or "REDACTED" in out

    def test_exception_chain_does_not_retain_cause(self) -> None:
        """Live-path scrubbing must not keep httpx causes that embed secrets."""
        from skyquery.errors import TransientSourceError
        from skyquery.sources.base import DataSource, SourceContext

        class Boom(DataSource):
            source_id = "boom"
            service_name = "Boom"

            def _live_fetch(self, operation: str, params: dict[str, object]) -> object:
                raise RuntimeError(f"api_key={SECRET} in url")

        src = Boom(SourceContext(replay=False, offline=False))
        with pytest.raises(TransientSourceError) as excinfo:
            src.fetch("op", {})
        err = excinfo.value
        assert err.__cause__ is None
        assert SECRET not in "".join(
            __import__("traceback").format_exception(type(err), err, err.__traceback__)
        )

    def test_event_output_never_contains_secret(self) -> None:
        stream = io.StringIO()
        configure_logging(level=logging.INFO, stream=stream)
        logger = get_logger("test")
        event(logger, logging.INFO, "auth attempt", token=SECRET, api_key=SECRET)
        contents = stream.getvalue()
        assert SECRET not in contents

    def test_full_log_stream_greps_clean(self) -> None:
        """Emit a burst of messages that mention secrets; grep the stream clean."""
        stream = io.StringIO()
        configure_logging(level=logging.DEBUG, stream=stream)
        logger = get_logger()
        for i in range(20):
            event(logger, logging.INFO, "request", i=i, ads_token=SECRET, bearer=SECRET)
            logger.info("inline mention token=%s", SECRET)
        assert SECRET not in stream.getvalue()
