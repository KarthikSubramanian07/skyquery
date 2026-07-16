"""Structured logging with credential redaction.

Logs go to stderr as key=value lines so they never pollute the MCP stdio channel
(which carries protocol JSON on stdout). Every message passes through a redactor
that masks anything resembling an API key or token, and a test greps all log
output to prove no credential ever escapes.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

_LOGGER_NAME = "skyquery"

# Patterns that look like secrets: long opaque tokens, and explicit key=value
# pairs whose key names a credential. These are masked before any line is emitted.
_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{24,}\b")
_BEARER_RE = re.compile(r"(?i)\b(bearer\s+)(\S+)")
_KV_SECRET_RE = re.compile(
    r"(?i)\b((?:api[_-]?key|token|secret|password|bearer|ads[_-]?token|nasa[_-]?key)"
    r"\s*[=:]\s*)(\S+)"
)
_MASK = "***REDACTED***"


def redact(text: str) -> str:
    """Mask anything that looks like a credential in ``text``."""
    text = _BEARER_RE.sub(rf"\1{_MASK}", text)
    text = _KV_SECRET_RE.sub(rf"\1{_MASK}", text)
    return _TOKEN_RE.sub(_MASK, text)


class RedactingFormatter(logging.Formatter):
    """A formatter that redacts credentials from the final rendered line."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the SkyQuery logger, or a child of it."""
    if name and name != _LOGGER_NAME:
        return logging.getLogger(f"{_LOGGER_NAME}.{name}")
    return logging.getLogger(_LOGGER_NAME)


def configure_logging(level: int = logging.INFO, *, stream: Any = None) -> None:
    """Configure the SkyQuery logger to write redacted lines to stderr."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    """Emit one structured, redacted key=value log line."""
    parts = [message]
    for key, value in fields.items():
        parts.append(f"{key}={value!r}")
    logger.log(level, redact(" ".join(parts)))
