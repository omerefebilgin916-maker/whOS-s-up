"""Network throughput, computed from the difference between two counter readings."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import psutil


@dataclass
class NetworkInfo:
    download_bytes_per_sec: float
    upload_bytes_per_sec: float


def _is_loopback(name: str) -> bool:
    lowered = name.lower()
    return lowered == "lo" or lowered.startswith("loopback")


def _read_counters() -> Dict[str, Tuple[int, int]]:
    """{interface: (bytes_recv, bytes_sent)} without loopback."""
    counters = psutil.net_io_counters(pernic=True) or {}
    return {name: (c.bytes_recv, c.bytes_sent)
            for name, c in counters.items() if not _is_loopback(name)}


class NetworkSampler:
    """Keeps the previous reading so each measure() returns the current speed."""

    def __init__(self) -> None:
        self._last_time: Optional[float] = None
        self._last_counters: Dict[str, Tuple[int, int]] = {}

    def prime(self) -> None:
        self._last_counters = _read_counters()
        self._last_time = time.monotonic()

    def measure(self) -> Optional[NetworkInfo]:
        """Speed since the previous reading; None on the very first call."""
        if self._last_time is None:
            self.prime()
            return None
        now = time.monotonic()
        counters = _read_counters()
        elapsed = now - self._last_time
        if elapsed <= 0:
            return None

        received = sent = 0
        for name, (recv, sent_total) in counters.items():
            previous = self._last_counters.get(name)
            if previous is None:
                continue
            received += max(0, recv - previous[0])
            sent += max(0, sent_total - previous[1])

        self._last_counters, self._last_time = counters, now
        return NetworkInfo(download_bytes_per_sec=received / elapsed,
                           upload_bytes_per_sec=sent / elapsed)
