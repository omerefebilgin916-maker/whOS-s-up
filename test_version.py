import contextlib
import io
import unittest
from pathlib import Path

from whosup import __version__
from whosup.cli import main


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = main(argv)
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue()


class VersionTests(unittest.TestCase):
    def test_version_flag(self):
        code, out = run(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f"whOS's up? {__version__}")

    def test_version_command(self):
        code, out = run(["version"])
        self.assertEqual(code, 0)
        self.assertEqual(out, f"whOS's up? v{__version__}\nSystem Status Monitor\n")

    def test_single_version_source(self):
        pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertIn('attr = "whosup.__version__"', pyproject)
        self.assertEqual(__version__, "0.1.1")

    def test_export_requires_format(self):
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = run(["export"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
