"""Process statistics (current user only by default) and 'possibly unexpected' rules.

Privacy rules for this module:
* Only processes owned by the current user are visible by default.
* The owner is used for filtering and is never stored or displayed.
* Command lines, working directories, environments, open files and
  executable paths are never read.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

import psutil

# Conservative thresholds: better to flag nothing than to flag wrongly.
HIGH_CPU_PERCENT = 80.0        # share of the WHOLE machine, not of one core
NEW_PROCESS_SECONDS = 120.0
SUSTAINED_SECONDS = 60.0


class ProcessScope(Enum):
    CURRENT_USER = "current_user"  # default
    ALL_USERS = "all_users"        # architecture only; no CLI flag in this version


@dataclass
class ProcessUsage:
    name: str
    ram_bytes: int
    cpu_percent: float  # share of the whole machine (0-100)
    instances: int = 1


@dataclass
class ProcessObservation:
    """The only view of a process that rules receive. Deliberately minimal."""

    name: str
    cpu_percent: float
    ram_bytes: int
    age_seconds: Optional[float]
    high_cpu_seconds: float  # how long CPU has stayed above HIGH_CPU_PERCENT


@dataclass
class Finding:
    """A process worth a closer look. NOT a verdict and never a security label."""

    name: str
    reason: str
    cpu_percent: Optional[float] = None
    network_bytes_per_sec: Optional[float] = None
    started_seconds_ago: Optional[float] = None


@dataclass
class ProcessSummary:
    total_count: int
    top: List[ProcessUsage] = field(default_factory=list)
    unexpected: List[Finding] = field(default_factory=list)


Rule = Callable[[ProcessObservation], Optional[Finding]]


def rule_new_and_busy(obs: ProcessObservation) -> Optional[Finding]:
    if (obs.age_seconds is not None and obs.age_seconds < NEW_PROCESS_SECONDS
            and obs.cpu_percent >= HIGH_CPU_PERCENT):
        return Finding(obs.name, "Recently started and using a lot of CPU",
                       cpu_percent=obs.cpu_percent, started_seconds_ago=obs.age_seconds)
    return None


def rule_sustained_high_cpu(obs: ProcessObservation) -> Optional[Finding]:
    if obs.high_cpu_seconds >= SUSTAINED_SECONDS:
        return Finding(obs.name, "High CPU usage for over a minute",
                       cpu_percent=obs.cpu_percent, started_seconds_ago=obs.age_seconds)
    return None


# Per-process network rate is not available from psutil, so no network rule exists.
RULES: List[Rule] = [rule_new_and_busy, rule_sustained_high_cpu]


def find_possibly_unexpected(observations: Iterable[ProcessObservation],
                             rules: Optional[List[Rule]] = None) -> List[Finding]:
    active = RULES if rules is None else rules
    findings: List[Finding] = []
    seen: Set[Tuple[str, str]] = set()
    for obs in observations:
        for rule in active:
            try:
                finding = rule(obs)
            except Exception:  # a broken rule must never break the app
                continue
            if finding is None:
                continue
            key = (finding.name, finding.reason)
            if key not in seen:
                seen.add(key)
                findings.append(finding)
            break  # one finding per process is enough
    return findings


@lru_cache(maxsize=1)
def _own_windows_identity() -> Optional[str]:
    try:
        return psutil.Process().username()  # compared only, never stored elsewhere
    except (psutil.Error, OSError):
        return None


def is_current_user(proc: "psutil.Process") -> bool:
    """True if the process belongs to the user running whosup."""
    getuid = getattr(os, "getuid", None)
    try:
        if getuid is not None:
            return proc.uids().real == getuid()
        identity = _own_windows_identity()
        return identity is not None and proc.username() == identity
    except (psutil.Error, OSError, AttributeError):
        return False  # when in doubt, hide the process


class ProcessSampler:
    """psutil.process_iter() reuses Process objects, so cpu_percent(None)
    measures the time since the previous call. prime() starts that clock."""

    def __init__(self, limit: int = 5, scope: ProcessScope = ProcessScope.CURRENT_USER) -> None:
        self.limit = limit
        self.scope = scope
        self._hot_since: Dict[Tuple[int, float], float] = {}

    def _visible(self):
        for proc in psutil.process_iter():
            if self.scope is ProcessScope.ALL_USERS or is_current_user(proc):
                yield proc

    def prime(self) -> None:
        for proc in self._visible():
            try:
                proc.cpu_percent(None)
            except psutil.Error:
                continue

    def collect(self) -> ProcessSummary:
        cores = psutil.cpu_count() or 1
        now_wall, now_mono, own_pid = time.time(), time.monotonic(), os.getpid()
        grouped: Dict[str, ProcessUsage] = {}
        observations: List[ProcessObservation] = []
        still_hot: Dict[Tuple[int, float], float] = {}
        total = 0

        for proc in self._visible():
            total += 1
            try:
                with proc.oneshot():
                    name = proc.name()
                    ram = proc.memory_info().rss
                    cpu = proc.cpu_percent(None) / cores
                    created = proc.create_time()
            except (psutil.Error, OSError):
                continue  # vanished or not permitted: still counted in total

            key = (proc.pid, created)
            if cpu >= HIGH_CPU_PERCENT:
                still_hot[key] = self._hot_since.get(key, now_mono)
            hot_for = now_mono - still_hot[key] if key in still_hot else 0.0

            if proc.pid != own_pid:
                observations.append(ProcessObservation(name, cpu, ram, now_wall - created, hot_for))

            entry = grouped.get(name)
            if entry is None:
                grouped[name] = ProcessUsage(name, ram, cpu)
            else:
                entry.ram_bytes += ram
                entry.cpu_percent += cpu
                entry.instances += 1

        self._hot_since = still_hot
        top = sorted(grouped.values(), key=lambda p: p.ram_bytes, reverse=True)[: self.limit]
        return ProcessSummary(total_count=total, top=top,
                              unexpected=find_possibly_unexpected(observations))
