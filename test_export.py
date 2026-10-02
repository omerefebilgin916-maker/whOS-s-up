import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from whosup.downloads import DownloadsInfo
from whosup.export import default_filename, to_markdown, to_text, write_export
from whosup.gpu import GpuInfo
from whosup.network import NetworkInfo
from whosup.power import PowerInfo
from whosup.processes import ProcessSummary, ProcessUsage
from whosup.storage import StorageInfo
from whosup.system import CpuInfo, MemoryInfo, Snapshot, take_snapshot

GB = 1024**3


def fixed_snapshot() -> Snapshot:
    """Hand-built snapshot so exporter output is deterministic (test input only)."""
    return Snapshot(
        timestamp=datetime(2026, 10, 1, 23, 42, 17),
        cpu=CpuInfo(37.0, 8, 4),
        memory=MemoryInfo(total=16 * GB, used=8 * GB, free=8 * GB, percent=50.0),
        gpu=GpuInfo(available=False),
        storage=StorageInfo("/", 1024 * GB, 412 * GB, 612 * GB, 41.2),
        network=NetworkInfo(8 * 1024**2, 1024**2),
        power=PowerInfo(has_battery=True, percent=73, plugged=True, status="Charging"),
        processes=ProcessSummary(10, [ProcessUsage("firefox", int(1.21 * GB), 12.0, 3)]),
        downloads=DownloadsInfo(message="No supported download sources detected"),
    )


class ExportTests(unittest.TestCase):
    def test_markdown(self):
        md = to_markdown(fixed_snapshot())
        self.assertIn("# whOS's up? \u2014 System Snapshot", md)
        self.assertIn("**Date:** 2026-10-01 23:42:17", md)
        self.assertIn("* CPU: 37%", md)
        self.assertIn("* GPU: Unavailable", md)
        self.assertIn("* Used: 412 GB  (41.2%)", md)
        self.assertIn("* Download: 8 MB/s", md)
        self.assertIn("| Process | RAM | CPU |", md)
        self.assertIn("| firefox (x3) | 1.21 GB | 12% |", md)
        self.assertIn("No supported download sources detected", md)

    def test_text(self):
        txt = to_text(fixed_snapshot())
        for heading in ("SYSTEM", "STORAGE", "NETWORK", "POWER", "TOP PROCESSES",
                        "DOWNLOADS", "POSSIBLY UNEXPECTED"):
            self.assertIn(heading, txt)
        self.assertIn("Battery:", txt)
        self.assertIn("firefox (x3)", txt)

    def test_no_battery_shows_not_available(self):
        snap = fixed_snapshot()
        snap.power = PowerInfo(has_battery=False)
        self.assertIn("Not available", to_text(snap))

    def test_missing_sections_do_not_crash(self):
        snap = fixed_snapshot()
        snap.cpu = snap.memory = snap.storage = snap.network = None
        snap.processes = snap.downloads = snap.power = None
        self.assertIn("Unavailable", to_markdown(snap))
        self.assertIn("Unavailable", to_text(snap))

    def test_default_filename(self):
        self.assertEqual(default_filename(fixed_snapshot(), "md"), "whosup-2026-10-01-234217.md")

    def test_write_files(self):
        snap = take_snapshot(sample_seconds=0.1)
        with tempfile.TemporaryDirectory() as folder:
            md_path = write_export(snap, "md", str(Path(folder) / "system.md"))
            txt_path = write_export(snap, "txt", str(Path(folder) / "system.txt"))
            self.assertTrue(md_path.read_text(encoding="utf-8").startswith("# whOS's up?"))
            self.assertTrue(txt_path.read_text(encoding="utf-8").startswith("whOS's up?"))
            self.assertRegex(default_filename(snap, "txt"), r"^whosup-\d{4}-\d{2}-\d{2}-\d{6}\.txt$")

    def test_bad_format(self):
        with self.assertRaises(ValueError):
            write_export(fixed_snapshot(), "pdf")


if __name__ == "__main__":
    unittest.main()
