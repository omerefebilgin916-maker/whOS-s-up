"""Active download detection through explicit, privacy-safe providers.

A provider implements detect() and returns DownloadItem objects.

Rules for providers (enforced by tests):
* no scanning of the file system, no directory walking;
* no reading of browser profiles, history, credentials or databases;
* no network access;
* anything file-related must call privacy.assert_not_sensitive() first.

DownloadItem.name is PRIVATE: it is shown on screen (path stripped) and is
never exported. Exports only receive the anonymous status, progress and speed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

import psutil

from .processes import is_current_user


@dataclass
class DownloadItem:
    source: str                              # PUBLIC: application or tool name
    status: str = "Active download"          # PUBLIC
    progress_percent: Optional[float] = None  # PUBLIC
    speed_bytes_per_sec: Optional[float] = None  # PUBLIC
    name: Optional[str] = None               # PRIVATE: may contain personal info


@dataclass
class DownloadsInfo:
    items: List[DownloadItem] = field(default_factory=list)
    message: str = ""


class DownloadProvider(Protocol):
    label: str

    def detect(self) -> List[DownloadItem]: ...


KNOWN_TOOLS = frozenset({"wget", "curl", "aria2c", "axel", "yt-dlp", "youtube-dl"})


class KnownDownloadToolsProvider:
    """Reports command-line download tools running under the current user.

    It only looks at process names: progress and speed are unknown, so none
    are shown, and the status says "running", not "downloading".
    """

    label = "known download tools"

    def detect(self) -> List[DownloadItem]:
        counts: Dict[str, int] = {}
        for proc in psutil.process_iter():
            if not is_current_user(proc):
                continue
            try:
                name = proc.name().lower()
            except (psutil.Error, OSError):
                continue
            if name.endswith(".exe"):
                name = name[:-4]
            if name in KNOWN_TOOLS:
                counts[name] = counts.get(name, 0) + 1
        return [
            DownloadItem(source=tool,
                         status="Download tool running" + (f" (x{n})" if n > 1 else ""))
            for tool, n in sorted(counts.items())
        ]


PROVIDERS: List[DownloadProvider] = [KnownDownloadToolsProvider()]


def detect_downloads(providers: Optional[List[DownloadProvider]] = None) -> DownloadsInfo:
    active = PROVIDERS if providers is None else providers
    if not active:
        return DownloadsInfo(message="No supported download sources detected")
    items: List[DownloadItem] = []
    for provider in active:
        try:
            items.extend(provider.detect())
        except Exception:
            continue
    return DownloadsInfo(
        items=items,
        message="" if items else "No active supported download tools detected",
    )
