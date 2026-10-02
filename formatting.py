"""Turns a Snapshot into display-neutral sections.

The terminal shows every section as built. Exports go through
public_sections(), which keeps only values explicitly marked PUBLIC.
Row and Section default to PRIVATE, so a new value added later stays
out of exports until someone deliberately marks it PUBLIC.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Tuple

from .privacy import Visibility, safe_display_name

if TYPE_CHECKING:  # pragma: no cover
    from .processes import Finding
    from .system import Snapshot

PUBLIC = Visibility.PUBLIC
PRIVATE = Visibility.PRIVATE
UNAVAILABLE = "Unavailable"
_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


@dataclass
class Row:
    label: str
    value: str
    severity: str = ""  # "", "warn", "crit", "muted"
    visibility: Visibility = PRIVATE


@dataclass
class Section:
    title: str
    rows: List[Row] = field(default_factory=list)
    lines: List[str] = field(default_factory=list)
    table_header: Tuple[str, ...] = ()
    table_rows: List[Tuple[str, ...]] = field(default_factory=list)
    visibility: Visibility = PRIVATE  # applies to lines and table (rows carry their own)


def _pub(label: str, value: str, severity: str = "") -> Row:
    return Row(label, value, severity, PUBLIC)


def format_bytes(size: float) -> str:
    """1024-based size with compact precision: 842 MB, 1.21 GB, 1 TB."""
    value = float(size)
    unit = 0
    while value >= 1024 and unit < len(_UNITS) - 1:
        value /= 1024
        unit += 1
    if unit == 0:
        return f"{int(value)} B"
    decimals = 0 if value >= 100 else 1 if value >= 10 else 2
    text = f"{value:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text} {_UNITS[unit]}"


def format_rate(bytes_per_second: float) -> str:
    return f"{format_bytes(bytes_per_second)}/s"


def format_percent(value: Optional[float], decimals: int = 0) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{value:.{decimals}f}%"


def format_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)} sec ago"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    return f"{int(seconds // 86400)} d ago"


def _severity_high(percent: Optional[float]) -> str:
    if percent is None:
        return "muted"
    if percent >= 90:
        return "crit"
    return "warn" if percent >= 75 else ""


def _severity_low(percent: Optional[float]) -> str:
    if percent is None:
        return "muted"
    if percent <= 15:
        return "crit"
    return "warn" if percent <= 30 else ""


def _mount_label(mount: str) -> str:
    """Show the mount point only when it is a filesystem root ('/', 'C:\\')."""
    return f"Disk ({mount})" if os.path.dirname(mount) == mount else "Disk"


def _system_section(snap: "Snapshot") -> Section:
    rows: List[Row] = []
    cpu, mem, gpu = snap.cpu, snap.memory, snap.gpu

    rows.append(_pub("CPU", format_percent(cpu.percent if cpu else None),
                     _severity_high(cpu.percent if cpu else None)))
    if cpu and cpu.logical:
        cores = (f"{cpu.physical} physical / {cpu.logical} logical"
                 if cpu.physical else f"{cpu.logical} logical")
        rows.append(_pub("Cores", cores))

    rows.append(_pub("RAM", format_percent(mem.percent if mem else None),
                     _severity_high(mem.percent if mem else None)))
    if mem:
        rows.append(_pub("RAM used", f"{format_bytes(mem.used)} / {format_bytes(mem.total)}"))
        rows.append(_pub("RAM free", format_bytes(mem.free)))

    if gpu and gpu.available and gpu.utilization_percent is not None:
        rows.append(_pub("GPU", format_percent(gpu.utilization_percent),
                         _severity_high(gpu.utilization_percent)))
        if gpu.name:
            rows.append(Row("GPU model", safe_display_name(gpu.name), "", PRIVATE))
    else:
        rows.append(_pub("GPU", UNAVAILABLE, "muted"))

    count = snap.processes.total_count if snap.processes else None
    rows.append(_pub("Processes", str(count) if count is not None else UNAVAILABLE,
                     "" if count is not None else "muted"))
    return Section("SYSTEM", rows=rows)


def _storage_section(snap: "Snapshot") -> Section:
    st = snap.storage
    if st is None:
        return Section("STORAGE", rows=[_pub("Disk", UNAVAILABLE, "muted")])
    return Section("STORAGE", rows=[
        _pub(_mount_label(st.mount), format_bytes(st.total)),
        _pub("Used", f"{format_bytes(st.used)}  ({format_percent(st.percent, 1)})", _severity_high(st.percent)),
        _pub("Free", format_bytes(st.free)),
    ])


def _network_section(snap: "Snapshot") -> Section:
    net = snap.network
    if net is None:
        return Section("NETWORK", rows=[_pub("Download", UNAVAILABLE, "muted"),
                                        _pub("Upload", UNAVAILABLE, "muted")])
    return Section("NETWORK", rows=[
        _pub("Download", format_rate(net.download_bytes_per_sec)),
        _pub("Upload", format_rate(net.upload_bytes_per_sec)),
    ])


def _power_section(snap: "Snapshot") -> Section:
    pw = snap.power
    if pw is None or not pw.has_battery:
        return Section("POWER", lines=["Not available"], visibility=PUBLIC)
    rows = [_pub("Battery", format_percent(pw.percent), _severity_low(pw.percent))]
    if pw.plugged is not None:
        rows.append(_pub("AC", "Connected" if pw.plugged else "Disconnected"))
    if pw.status:
        rows.append(_pub("Status", pw.status))
    return Section("POWER", rows=rows)


def _processes_section(snap: "Snapshot") -> Section:
    summary = snap.processes
    if summary is None or not summary.top:
        return Section("TOP PROCESSES", lines=[UNAVAILABLE], visibility=PUBLIC)
    table_rows = []
    for item in summary.top:
        name = safe_display_name(item.name)
        name = f"{name} (x{item.instances})" if item.instances > 1 else name
        table_rows.append((name, format_bytes(item.ram_bytes), f"{item.cpu_percent:.0f}%"))
    return Section("TOP PROCESSES", table_header=("Process", "RAM", "CPU"),
                   table_rows=table_rows, visibility=PUBLIC)


def _downloads_section(snap: "Snapshot") -> Section:
    info = snap.downloads
    if info is None:
        return Section("DOWNLOADS", lines=[UNAVAILABLE], visibility=PUBLIC)
    if not info.items:
        return Section("DOWNLOADS", lines=[info.message], visibility=PUBLIC)
    rows: List[Row] = []
    for item in info.items:
        bits = [item.status]
        if item.progress_percent is not None:
            bits.append(format_percent(item.progress_percent))
        if item.speed_bytes_per_sec is not None:
            bits.append(format_rate(item.speed_bytes_per_sec))
        rows.append(_pub(safe_display_name(item.source), "  ".join(bits)))
        if item.name:  # file names can be personal: screen only
            rows.append(Row("File", safe_display_name(item.name), "", PRIVATE))
    return Section("DOWNLOADS", rows=rows)


def format_finding(finding: "Finding") -> List[str]:
    bits = [safe_display_name(finding.name)]
    if finding.cpu_percent is not None:
        bits.append(f"CPU {finding.cpu_percent:.0f}%")
    if finding.network_bytes_per_sec is not None:
        bits.append(f"Network {format_rate(finding.network_bytes_per_sec)}")
    if finding.started_seconds_ago is not None:
        bits.append(f"Started {format_age(finding.started_seconds_ago)}")
    return ["  ".join(bits), f"Reason: {finding.reason}"]


def _unexpected_section(snap: "Snapshot") -> Section:
    findings = snap.processes.unexpected if snap.processes else []
    if not findings:
        return Section("POSSIBLY UNEXPECTED", lines=["None detected"], visibility=PUBLIC)
    lines: List[str] = []
    for finding in findings:
        lines.extend(format_finding(finding))
    lines.append("Worth a closer look. This is not a security verdict.")
    return Section("POSSIBLY UNEXPECTED", lines=lines, visibility=PUBLIC)


def build_sections(snap: "Snapshot") -> List[Section]:
    """Everything the screen shows."""
    return [
        _system_section(snap),
        _storage_section(snap),
        _network_section(snap),
        _power_section(snap),
        _processes_section(snap),
        _downloads_section(snap),
        _unexpected_section(snap),
    ]


def public_sections(sections: List[Section]) -> List[Section]:
    """Only what is explicitly PUBLIC: this is all an export may contain."""
    result: List[Section] = []
    for section in sections:
        rows = [row for row in section.rows if row.visibility is PUBLIC]
        section_public = section.visibility is PUBLIC
        lines = list(section.lines) if section_public else []
        table_rows = list(section.table_rows) if section_public else []
        if rows or lines or table_rows:
            result.append(Section(section.title, rows, lines,
                                  section.table_header if table_rows else (),
                                  table_rows, section.visibility))
    return result
