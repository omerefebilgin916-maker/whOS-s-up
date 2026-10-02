import os
import re
import socket
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_export import fixed_snapshot
from whosup.cli import main
from whosup.downloads import DownloadItem, DownloadsInfo
from whosup.export import default_filename, to_markdown, to_text, write_export
from whosup.formatting import Row, Section, build_sections, public_sections
from whosup.privacy import (
    Visibility, assert_not_sensitive, is_sensitive_path, safe_display_name, safe_error_message,
)
from whosup.processes import Finding, ProcessSummary, ProcessUsage
from whosup.system import take_snapshot

PERSONAL_NAME = "/home/omer/Documents/\u00d6mer_Efe_LGS_Program\u0131.pdf"
IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
MAC = re.compile(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b")


def screen_text(snapshot):
    parts = []
    for s in build_sections(snapshot):
        parts += [f"{r.label} {r.value}" for r in s.rows] + s.lines
        parts += [" ".join(row) for row in s.table_rows]
    return "\n".join(parts)


def without_process_names(snapshot):
    snapshot.processes = None
    snapshot.downloads = None
    return snapshot


class VisibilityTests(unittest.TestCase):
    def test_new_fields_are_private_by_default(self):
        self.assertIs(Row("Secret", "x").visibility, Visibility.PRIVATE)
        self.assertIs(Section("NEW", lines=["leak?"]).visibility, Visibility.PRIVATE)

    def test_private_values_never_reach_public_view(self):
        sections = [Section("NEW", rows=[Row("Secret", "hunter2"), Row("Ok", "1", "", Visibility.PUBLIC)],
                            lines=["also secret"], table_header=("a",), table_rows=[("secret-cell",)])]
        (public,) = public_sections(sections)
        self.assertEqual([r.label for r in public.rows], ["Ok"])
        self.assertEqual(public.lines, [])
        self.assertEqual(public.table_rows, [])

    def test_fully_private_section_is_dropped(self):
        self.assertEqual(public_sections([Section("ONLY", rows=[Row("a", "b")])]), [])

    def test_export_excludes_private_rows_added_to_screen(self):
        snap = fixed_snapshot()
        extra = Section("FUTURE", rows=[Row("Serial", "SN-12345")])
        with mock.patch("whosup.export.build_sections", return_value=build_sections(snap) + [extra]):
            self.assertNotIn("SN-12345", to_markdown(snap))
            self.assertNotIn("SN-12345", to_text(snap))
            self.assertNotIn("FUTURE", to_text(snap))


class ExportRedactionTests(unittest.TestCase):
    def snapshot_with_download(self):
        snap = fixed_snapshot()
        snap.downloads = DownloadsInfo(items=[DownloadItem(
            "Firefox", progress_percent=74.0, speed_bytes_per_sec=12.4 * 1024**2, name=PERSONAL_NAME)])
        return snap

    def test_download_name_is_anonymous_in_exports(self):
        snap = self.snapshot_with_download()
        for text in (to_markdown(snap), to_text(snap)):
            for leak in ("Efe", "LGS", "\u00d6mer", "/home", "omer", ".pdf"):
                self.assertNotIn(leak, text)
            self.assertIn("Firefox", text)
            self.assertIn("Active download", text)
            self.assertIn("74%", text)
            self.assertIn("12.4 MB/s", text)

    def test_screen_shows_name_without_path(self):
        shown = screen_text(self.snapshot_with_download())
        self.assertIn("\u00d6mer_Efe_LGS_Program\u0131.pdf", shown)
        self.assertNotIn("/home", shown)
        self.assertNotIn("Documents", shown)

    def test_findings_export_only_generic_fields(self):
        snap = fixed_snapshot()
        snap.processes = ProcessSummary(3, [ProcessUsage("tool", 1024, 1.0)], [
            Finding("tool", "Recently started and using a lot of CPU", cpu_percent=90, started_seconds_ago=30)])
        md = to_markdown(snap)
        self.assertIn("Recently started and using a lot of CPU", md)
        self.assertIn("not a security verdict", md)
        for word in ("virus", "malware", "trojan", "dangerous", "malicious"):
            self.assertNotIn(word, md.lower())

    def test_filename_has_no_personal_info(self):
        self.assertRegex(default_filename(take_snapshot(0.05), "md"), r"^whosup-\d{4}-\d{2}-\d{2}-\d{6}\.md$")

    @unittest.skipUnless(hasattr(os, "getuid"), "POSIX permissions")
    def test_new_export_is_owner_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_export(fixed_snapshot(), "md", str(Path(folder) / "s.md"))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)


class OutputHygieneTests(unittest.TestCase):
    def outputs(self, snap):
        return [screen_text(snap), to_markdown(snap), to_text(snap)]

    def test_no_sentinel_identity_in_any_output(self):
        env = {"USER": "zz-sentinel-user", "LOGNAME": "zz-sentinel-user", "HOSTNAME": "zz-sentinel-host"}
        with mock.patch.dict(os.environ, env), mock.patch("socket.gethostname", return_value="zz-sentinel-host"):
            for text in self.outputs(take_snapshot(0.05)):
                self.assertNotIn("zz-sentinel", text)

    def test_real_username_hostname_home_absent(self):
        snap = without_process_names(take_snapshot(0.05))  # process names are arbitrary user-facing text
        secrets = {socket.gethostname()}
        try:
            import pwd
            secrets.add(pwd.getpwuid(os.getuid()).pw_name)
        except ImportError:
            pass
        home = str(Path.home())
        for text in self.outputs(snap):
            for secret in filter(None, secrets):
                self.assertIsNone(re.search(rf"(?<![\w.-]){re.escape(secret)}(?![\w.-])", text),
                                  "identity value found in output")
            if home not in ("/", ""):
                self.assertNotIn(home, text)

    def test_no_ip_or_mac_in_any_output(self):
        for text in self.outputs(take_snapshot(0.05)):
            self.assertIsNone(IPV4.search(text))
            self.assertIsNone(MAC.search(text))

    def test_no_environment_or_path_variable_data(self):
        with mock.patch.dict(os.environ, {"AWS_SECRET_ACCESS_KEY": "zz-secret-value", "PATH": "/zz/bin"}):
            for text in self.outputs(take_snapshot(0.05)):
                self.assertNotIn("zz-secret-value", text)
                self.assertNotIn("/zz/bin", text)

    def test_mount_label_hides_non_root_paths(self):
        snap = fixed_snapshot()
        snap.storage.mount = "/home/omer/data"
        for text in self.outputs(snap):
            self.assertNotIn("omer", text)


class PrivacyHelpersTests(unittest.TestCase):
    def test_sensitive_paths(self):
        for path in ("/home/u/.mozilla/firefox/x/cookies.sqlite", "C:\\Users\\u\\AppData\\Chrome\\Login Data",
                     "/home/u/.ssh/id_rsa", "/home/u/.config/google-chrome/Default/History",
                     "/home/u/.mozilla/firefox/x/places.sqlite"):
            self.assertTrue(is_sensitive_path(path), path)
            with self.assertRaises(PermissionError) as ctx:
                assert_not_sensitive(path)
            self.assertNotIn("home", str(ctx.exception))
        self.assertFalse(is_sensitive_path("/tmp/report.txt"))

    def test_safe_display_name(self):
        self.assertEqual(safe_display_name("/a/b/c/file.iso"), "file.iso")
        self.assertEqual(safe_display_name("C:\\Users\\x\\f.zip"), "f.zip")
        self.assertEqual(safe_display_name("a\x00b\x1bc"), "abc")
        self.assertLessEqual(len(safe_display_name("x" * 500)), 40)

    def test_error_messages_carry_no_paths(self):
        err = PermissionError(13, "Permission denied", "/home/omer/secret.md")
        self.assertNotIn("omer", safe_error_message(err))
        self.assertNotIn("secret", safe_error_message(ValueError("/home/omer/x")))

    def test_cli_error_has_no_path_or_traceback(self):
        import contextlib, io
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = main(["export", "--md", "--output", "/nonexistent-zz/omer/system.md"])
        self.assertEqual(code, 1)
        self.assertNotIn("omer", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


if __name__ == "__main__":
    unittest.main()
