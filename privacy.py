"""Privacy primitives shared by the whole app.

* Visibility: every value shown by whOS's up? is PUBLIC or PRIVATE.
  Exports contain PUBLIC values only, and anything that is not explicitly
  marked PUBLIC stays PRIVATE, so a future field cannot leak by accident.
* Helpers that strip paths from names and turn errors into generic messages.
"""

from __future__ import annotations

import re
from enum import Enum


class Visibility(Enum):
    PUBLIC = "public"    # safe to appear in exports
    PRIVATE = "private"  # on-screen only, never exported


# Locations no provider may ever read (browser data, keys, credentials, history).
_SENSITIVE_MARKERS = (
    "cookies", "history", "login data", "logins.json", "key4.db", "key3.db",
    "places.sqlite", "formhistory", "web data", "session", "/.ssh", "/.gnupg",
    "/.aws", "/.netrc", "credentials", "id_rsa", "id_ed25519", "shadow",
    "keychain", "/etc/passwd", "bash_history", "zsh_history",
)
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def is_sensitive_path(path: object) -> bool:
    lowered = str(path).replace("\\", "/").lower()
    return any(marker in lowered for marker in _SENSITIVE_MARKERS)


def assert_not_sensitive(path: object) -> None:
    """Call before any file access in a provider. The message never echoes the path."""
    if is_sensitive_path(path):
        raise PermissionError("refusing to read a sensitive location")


def safe_display_name(name: object, max_length: int = 40) -> str:
    """Last path component only, control characters removed, length limited."""
    last = re.split(r"[\\/]", str(name))[-1]
    cleaned = _CONTROL_CHARS.sub("", last).strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1] + "\u2026"
    return cleaned


def safe_error_message(error: BaseException) -> str:
    """Generic, path-free description of an error (no username, no file names)."""
    if isinstance(error, PermissionError):
        return "permission denied"
    if isinstance(error, FileNotFoundError):
        return "file or directory not found"
    if isinstance(error, IsADirectoryError):
        return "the output path is a directory"
    if isinstance(error, OSError):
        return "could not access the file system"
    return f"unexpected error ({type(error).__name__})"
