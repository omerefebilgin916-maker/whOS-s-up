import unittest

from whosup.formatting import format_bytes, format_percent, format_rate, build_sections


class FormattingTests(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(format_bytes(842 * 1024**2), "842 MB")
        self.assertEqual(format_bytes(int(1.21 * 1024**3)), "1.21 GB")
        self.assertEqual(format_bytes(412 * 1024**3), "412 GB")
        self.assertEqual(format_bytes(1024**4), "1 TB")
        self.assertEqual(format_bytes(0), "0 B")

    def test_rate_and_percent(self):
        self.assertEqual(format_rate(2 * 1024**2), "2 MB/s")
        self.assertEqual(format_percent(41.23, 1), "41.2%")
        self.assertEqual(format_percent(None), "Unavailable")

    def test_process_label_is_generic(self):
        from tests.test_export import fixed_snapshot
        text = "\n".join(
            f"{r.label}: {r.value}"
            for section in build_sections(fixed_snapshot())
            for r in section.rows
        )
        self.assertIn("Processes: 10", text)
        self.assertNotIn("Your processes", text)

    def test_storage_layout_is_explicit(self):
        from tests.test_export import fixed_snapshot
        storage = next(s for s in build_sections(fixed_snapshot()) if s.title == "STORAGE")
        pairs = {row.label: row.value for row in storage.rows}
        self.assertEqual(pairs["Disk (/)"], "1 TB")
        self.assertEqual(pairs["Used"], "412 GB  (41.2%)")
        self.assertEqual(pairs["Free"], "612 GB")

if __name__ == "__main__":
    unittest.main()
