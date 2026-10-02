"""Terminal rendering with rich: one-shot view and live watch mode."""

from __future__ import annotations

import sys
import time
from typing import List

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from . import __app_name__, __version__
from .formatting import Section, build_sections
from .system import Snapshot, SnapshotCollector, take_snapshot

SEVERITY_STYLES = {"": "", "warn": "yellow", "crit": "bold red", "muted": "dim"}
ARROWS = {"Download": "\u2193 ", "Upload": "\u2191 "}


def _render_section(section: Section) -> List[RenderableType]:
    parts: List[RenderableType] = [
        Text(section.title, style="bold cyan"),
        Rule(characters="\u2500", style="dim"),
    ]
    if section.rows:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", no_wrap=True)
        grid.add_column(overflow="fold")
        for row in section.rows:
            grid.add_row(Text(ARROWS.get(row.label, "") + row.label),
                         Text(row.value, style=SEVERITY_STYLES.get(row.severity, "")))
        parts.append(grid)
    for line in section.lines:
        parts.append(Text(line))
    if section.table_rows:
        grid = Table.grid(padding=(0, 2), expand=True)
        grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        grid.add_column(justify="right", no_wrap=True)
        grid.add_column(style="dim", no_wrap=True)
        grid.add_column(justify="right", no_wrap=True)
        for name, ram, cpu in section.table_rows:
            grid.add_row(Text(name), Text(ram), Text("CPU"), Text(cpu))
        parts.append(grid)
    return parts


def render_snapshot(snapshot: Snapshot) -> RenderableType:
    header = Table.grid(expand=True)
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(Text(__app_name__, style="bold magenta"),
                   Text(f"{snapshot.timestamp:%H:%M:%S}", style="dim"))

    parts: List[RenderableType] = [header, Text("")]
    for section in build_sections(snapshot):
        parts.extend(_render_section(section))
        parts.append(Text(""))
    parts.append(Text(f"{__app_name__} v{__version__}", style="dim"))
    return Group(*parts)


def show_once() -> None:
    """Print a single snapshot and return."""
    Console().print(render_snapshot(take_snapshot()))


def run_watch(interval: float) -> int:
    """Live monitor on the alternate screen; Ctrl+C restores the terminal."""
    if not sys.stdout.isatty():
        print("whosup watch needs an interactive terminal.", file=sys.stderr)
        return 2

    console = Console()
    collector = SnapshotCollector()
    collector.prime()
    delay = min(interval, 0.5)  # show the first frame quickly
    try:
        with Live(console=console, screen=True, auto_refresh=False) as live:
            while True:
                time.sleep(delay)
                started = time.monotonic()
                live.update(render_snapshot(collector.collect()), refresh=True)
                delay = max(0.0, interval - (time.monotonic() - started))
    except KeyboardInterrupt:
        pass  # Live.__exit__ has already restored the screen and cursor
    return 0
