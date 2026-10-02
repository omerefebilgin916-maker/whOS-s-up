"""Static checks on the source code: no network, no telemetry, no sensitive reads."""

import ast
import unittest
from pathlib import Path

from whosup import gpu
from whosup.downloads import KnownDownloadToolsProvider, detect_downloads
from tests.fakes import FakeProc

PACKAGE = Path(__file__).resolve().parent.parent / "whosup"
SOURCES = sorted(PACKAGE.glob("*.py"))

NETWORK_MODULES = {"socket", "urllib", "urllib3", "http", "requests", "httpx", "aiohttp", "ftplib",
                   "smtplib", "telnetlib", "xmlrpc", "websocket", "websockets", "ssl", "webbrowser",
                   "sentry_sdk", "posthog", "mixpanel", "analytics", "telemetry", "asyncio"}
IDENTITY_NAMES = {"net_connections", "net_if_addrs", "gethostname", "getfqdn", "getuser", "getlogin",
                  "cmdline", "environ", "getenv", "cwd", "open_files", "connections", "uname", "node",
                  "home", "expanduser"}
FILE_SEARCH_NAMES = {"walk", "rglob", "glob", "listdir", "scandir", "expanduser", "home", "open",
                     "read_text", "read_bytes"}
DOWNLOAD_FORBIDDEN_IMPORTS = {"sqlite3", "glob", "fnmatch", "shutil", "os", "pathlib", "subprocess",
                              "configparser", "plistlib", "zipfile", "tarfile", "json"}
SENSITIVE_STRINGS = ("cookie", "history", "login data", "logins.json", "places.sqlite", "key4",
                     "password", "credential", "token", ".ssh")


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def imports(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def identifiers(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Name):
            found.add(node.id)
    return found


def string_constants(tree):
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
                docstrings.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


class NoNetworkOrTelemetryTests(unittest.TestCase):
    def test_sources_found(self):
        self.assertGreaterEqual(len(SOURCES), 10)

    def test_no_network_or_telemetry_imports(self):
        for path in SOURCES:
            self.assertFalse(imports(parse(path)) & NETWORK_MODULES, path.name)

    def test_no_urls_in_code(self):
        for path in SOURCES:
            for text in string_constants(parse(path)):
                self.assertNotRegex(text.lower(), r"https?://|wss?://", path.name)

    def test_no_identity_collection_apis(self):
        for path in SOURCES:
            self.assertFalse(identifiers(parse(path)) & IDENTITY_NAMES, path.name)

    def test_username_api_only_in_ownership_check(self):
        for path in SOURCES:
            uses = "username" in identifiers(parse(path))
            self.assertEqual(uses, path.name == "processes.py", path.name)

    def test_subprocess_only_in_gpu_with_fixed_arguments(self):
        for path in SOURCES:
            self.assertEqual("subprocess" in imports(parse(path)), path.name == "gpu.py", path.name)
        for node in ast.walk(parse(PACKAGE / "gpu.py")):
            if isinstance(node, ast.keyword) and node.arg == "shell":
                self.fail("shell= must not be used")

    def test_nvidia_query_has_no_identifying_fields(self):
        for forbidden in ("serial", "uuid", "pci", "driver"):
            self.assertNotIn(forbidden, gpu.NVIDIA_QUERY.lower())


class DownloadProviderSafetyTests(unittest.TestCase):
    def provider_files(self):
        return sorted(PACKAGE.glob("downloads*.py"))

    def test_provider_code_cannot_scan_or_open_files(self):
        for path in self.provider_files():
            tree = parse(path)
            self.assertFalse(imports(tree) & DOWNLOAD_FORBIDDEN_IMPORTS, path.name)
            self.assertFalse(identifiers(tree) & FILE_SEARCH_NAMES, path.name)

    def test_provider_code_mentions_no_browser_or_credential_locations(self):
        for path in self.provider_files():
            for text in string_constants(parse(path)):
                lowered = text.lower()
                for marker in SENSITIVE_STRINGS:
                    self.assertNotIn(marker, lowered, f"{path.name}: {marker}")

    def test_builtin_provider_uses_process_names_only(self):
        import os
        from unittest import mock
        if not hasattr(os, "getuid"):
            self.skipTest("POSIX only")
        me = os.getuid()
        procs = [FakeProc(1, "wget", me), FakeProc(2, "wget", me), FakeProc(3, "curl", me + 1),
                 FakeProc(4, "firefox", me)]
        with mock.patch("whosup.downloads.psutil.process_iter", return_value=procs):
            items = KnownDownloadToolsProvider().detect()
        self.assertEqual([(i.source, i.status) for i in items], [("wget", "Download tool running (x2)")])
        self.assertIsNone(items[0].name)
        self.assertIsNone(items[0].progress_percent)

    def test_messages(self):
        self.assertEqual(detect_downloads([]).message, "No supported download sources detected")
        class Empty:
            label = "empty"
            def detect(self): return []
        self.assertIn("No active", detect_downloads([Empty()]).message)

    def test_failing_provider_does_not_crash(self):
        class Broken:
            label = "broken"
            def detect(self): raise RuntimeError("/home/omer/x")
        info = detect_downloads([Broken()])
        self.assertEqual(info.items, [])
        self.assertNotIn("omer", info.message)


if __name__ == "__main__":
    unittest.main()
