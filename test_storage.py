import tempfile
import unittest

from whosup.storage import read_storage


class StorageTests(unittest.TestCase):
    def test_default_disk(self):
        st = read_storage()
        self.assertGreater(st.total, 0)
        self.assertLessEqual(st.used, st.total)
        self.assertTrue(0 <= st.percent <= 100)

    def test_explicit_path(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertGreater(read_storage(folder).total, 0)


if __name__ == "__main__":
    unittest.main()
