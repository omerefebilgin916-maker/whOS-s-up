import unittest

from whosup.processes import ProcessSampler
from whosup.system import read_cpu, read_memory, take_snapshot


class SystemTests(unittest.TestCase):
    def test_cpu(self):
        cpu = read_cpu()
        self.assertGreaterEqual(cpu.percent, 0)
        self.assertLessEqual(cpu.percent, 100)
        self.assertGreaterEqual(cpu.logical, 1)

    def test_memory(self):
        mem = read_memory()
        self.assertGreater(mem.total, 0)
        self.assertEqual(mem.used + mem.free, mem.total)
        self.assertTrue(0 <= mem.percent <= 100)

    def test_processes(self):
        sampler = ProcessSampler(limit=3)
        sampler.prime()
        summary = sampler.collect()
        self.assertGreater(summary.total_count, 0)
        self.assertLessEqual(len(summary.top), 3)
        rams = [p.ram_bytes for p in summary.top]
        self.assertEqual(rams, sorted(rams, reverse=True))

    def test_snapshot(self):
        snap = take_snapshot(sample_seconds=0.1)
        self.assertIsNotNone(snap.timestamp)
        self.assertIsNotNone(snap.cpu)
        self.assertIsNotNone(snap.memory)
        self.assertIsNotNone(snap.storage)
        self.assertIsNotNone(snap.downloads)


if __name__ == "__main__":
    unittest.main()
