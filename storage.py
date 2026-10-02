"""Disk usage of the main system disk."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional

import psutil


@dataclass
class StorageInfo:
    mount: str
    total: int
    used: int
    free: int
    percent: float


def default_storage_path() -> str:
    """Filesystem root ('/' on Linux, the current drive root on Windows)."""
    return os.path.abspath(os.sep)


def read_storage(path: Optional[str] = None) -> StorageInfo:
    mount = path or default_storage_path()
    usage = psutil.disk_usage(mount)
    return StorageInfo(mount=mount, total=usage.total, used=usage.used,
                       free=usage.free, percent=usage.percent)
