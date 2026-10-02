"""Battery / AC state. Desktops without a battery report has_battery=False."""

from __future__ import annotations

import glob
import sys
from dataclasses import dataclass
from typing import Optional

import psutil


@dataclass
class PowerInfo:
    has_battery: bool
    percent: Optional[float] = None
    plugged: Optional[bool] = None
    status: Optional[str] = None  # Charging / Discharging / Full ...


def _linux_battery_status() -> Optional[str]:
    """Real charging state from sysfs, when the kernel exposes it."""
    for path in sorted(glob.glob("/sys/class/power_supply/BAT*/status")):
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read().strip()
        except OSError:
            continue
        if text and text.lower() != "unknown":
            return text
    return None


def read_power() -> PowerInfo:
    sensors = getattr(psutil, "sensors_battery", None)
    if sensors is None:
        return PowerInfo(has_battery=False)
    try:
        battery = sensors()
    except (OSError, NotImplementedError):
        return PowerInfo(has_battery=False)
    if battery is None:
        return PowerInfo(has_battery=False)

    status = _linux_battery_status() if sys.platform.startswith("linux") else None
    if status is None and battery.power_plugged is False:
        status = "Discharging"
    return PowerInfo(has_battery=True, percent=battery.percent,
                     plugged=battery.power_plugged, status=status)
