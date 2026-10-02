"""GPU usage through pluggable providers.

A provider is a function returning GpuInfo or None. Add new vendors or
platforms by appending to PROVIDERS. When no provider succeeds, the GPU is
reported as unavailable - nothing is ever guessed.
"""

from __future__ import annotations

import glob
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class GpuInfo:
    available: bool
    name: Optional[str] = None
    utilization_percent: Optional[float] = None
    memory_used: Optional[int] = None  # bytes
    memory_total: Optional[int] = None  # bytes


# Only usage figures and the model name: no serial number, no UUID.
NVIDIA_QUERY = "name,utilization.gpu,memory.used,memory.total"


def _nvidia_smi() -> Optional[GpuInfo]:
    if shutil.which("nvidia-smi") is None:
        return None
    result = subprocess.run(
        ["nvidia-smi",
         f"--query-gpu={NVIDIA_QUERY}",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=3, check=True,
    )
    lines = result.stdout.strip().splitlines()
    if not lines:
        return None
    name, util, mem_used, mem_total = [part.strip() for part in lines[0].split(",")]
    mib = 1024 * 1024
    return GpuInfo(True, name, float(util), int(float(mem_used) * mib), int(float(mem_total) * mib))


def _read_text(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _amd_sysfs() -> Optional[GpuInfo]:
    """amdgpu exposes busy percentage through sysfs on Linux."""
    if not sys.platform.startswith("linux"):
        return None
    for busy_path in sorted(glob.glob("/sys/class/drm/card[0-9]*/device/gpu_busy_percent")):
        busy = _read_text(busy_path)
        if busy is None or not busy.isdigit():
            continue
        name = _read_text(busy_path.replace("gpu_busy_percent", "product_name")) or "AMD GPU"
        return GpuInfo(True, name, float(busy))
    return None


PROVIDERS: List[Callable[[], Optional[GpuInfo]]] = [_nvidia_smi, _amd_sysfs]


def read_gpu() -> GpuInfo:
    for provider in PROVIDERS:
        try:
            info = provider()
        except Exception:  # a broken driver tool must never break the app
            info = None
        if info is not None:
            return info
    return GpuInfo(available=False)
