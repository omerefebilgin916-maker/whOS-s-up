"""CPU / RAM readers and the single snapshot shared by screen and exports."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, TypeVar

import psutil

from .downloads import DownloadsInfo, detect_downloads
from .gpu import GpuInfo, read_gpu
from .network import NetworkInfo, NetworkSampler
from .power import PowerInfo, read_power
from .processes import ProcessSampler, ProcessSummary
from .storage import StorageInfo, read_storage

T = TypeVar("T")


@dataclass
class CpuInfo:
    percent: float
    logical: Optional[int]
    physical: Optional[int]


@dataclass
class MemoryInfo:
    total: int
    used: int
    free: int
    percent: float


@dataclass
class Snapshot:
    timestamp: datetime
    cpu: Optional[CpuInfo]
    memory: Optional[MemoryInfo]
    gpu: Optional[GpuInfo]
    storage: Optional[StorageInfo]
    network: Optional[NetworkInfo]
    power: Optional[PowerInfo]
    processes: Optional[ProcessSummary]
    downloads: Optional[DownloadsInfo]


def read_cpu() -> CpuInfo:
    """CPU usage since the previous call (prime once before relying on it)."""
    return CpuInfo(
        percent=psutil.cpu_percent(interval=None),
        logical=psutil.cpu_count(logical=True),
        physical=psutil.cpu_count(logical=False),
    )


def read_memory() -> MemoryInfo:
    vm = psutil.virtual_memory()
    used = vm.total - vm.available
    return MemoryInfo(total=vm.total, used=used, free=vm.available,
                      percent=used / vm.total * 100 if vm.total else 0.0)


def _safe(reader: Callable[[], T]) -> Optional[T]:
    """One failing section must never take the whole program down."""
    try:
        return reader()
    except Exception:
        return None


class SnapshotCollector:
    """Holds the state needed for rates (CPU, network, per-process CPU)."""

    def __init__(self, process_limit: int = 5) -> None:
        self._network = NetworkSampler()
        self._processes = ProcessSampler(limit=process_limit)

    def prime(self) -> None:
        _safe(lambda: psutil.cpu_percent(interval=None))
        _safe(self._network.prime)
        _safe(self._processes.prime)

    def collect(self) -> Snapshot:
        return Snapshot(
            timestamp=datetime.now(),
            cpu=_safe(read_cpu),
            memory=_safe(read_memory),
            gpu=_safe(read_gpu),
            storage=_safe(read_storage),
            network=_safe(self._network.measure),
            power=_safe(read_power),
            processes=_safe(self._processes.collect),
            downloads=_safe(detect_downloads),
        )


def take_snapshot(sample_seconds: float = 0.5) -> Snapshot:
    """One-shot snapshot: prime, wait briefly so rates exist, then read."""
    collector = SnapshotCollector()
    collector.prime()
    time.sleep(sample_seconds)
    return collector.collect()
