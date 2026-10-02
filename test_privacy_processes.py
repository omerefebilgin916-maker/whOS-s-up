import dataclasses
import os
import unittest
from unittest import mock

import psutil

from tests.fakes import FakeProc
from whosup.processes import (
    HIGH_CPU_PERCENT, NEW_PROCESS_SECONDS, SUSTAINED_SECONDS, RULES, Finding,
    ProcessObservation, ProcessSampler, ProcessScope, ProcessSummary, ProcessUsage,
    find_possibly_unexpected, is_current_user, rule_new_and_busy, rule_sustained_high_cpu,
)

POSIX = hasattr(os, "getuid")
FORBIDDEN_FIELDS = {"cmdline", "cwd", "environ", "env", "username", "user", "uid", "exe",
                    "path", "open_files", "connections", "hostname", "home"}
FORBIDDEN_WORDS = ("virus", "malware", "trojan", "dangerous", "malicious")


@unittest.skipUnless(POSIX, "uid filtering is POSIX-specific")
class CurrentUserFilteringTests(unittest.TestCase):
    def setUp(self):
        self.me = os.getuid()

    def test_is_current_user(self):
        self.assertTrue(is_current_user(FakeProc(1, "mine", self.me)))
        self.assertFalse(is_current_user(FakeProc(2, "theirs", self.me + 1)))

    def test_unreadable_owner_is_hidden(self):
        self.assertFalse(is_current_user(FakeProc(3, "x", self.me, deny=True)))

    def test_other_users_are_not_shown_or_counted(self):
        procs = [FakeProc(1, "mine-a", self.me, rss=5 * 1024**2),
                 FakeProc(2, "othersecret", self.me + 1, rss=900 * 1024**2),
                 FakeProc(3, "mine-b", self.me, rss=7 * 1024**2)]
        with mock.patch("whosup.processes.psutil.process_iter", return_value=procs):
            summary = ProcessSampler(limit=10).collect()
        names = [p.name for p in summary.top]
        self.assertEqual(summary.total_count, 2)
        self.assertNotIn("othersecret", names)
        self.assertEqual(names, ["mine-b", "mine-a"])

    def test_all_users_scope_exists_but_is_not_default(self):
        self.assertIs(ProcessSampler().scope, ProcessScope.CURRENT_USER)
        procs = [FakeProc(1, "a", self.me), FakeProc(2, "b", self.me + 1)]
        with mock.patch("whosup.processes.psutil.process_iter", return_value=procs):
            summary = ProcessSampler(scope=ProcessScope.ALL_USERS).collect()
        self.assertEqual(summary.total_count, 2)

    def test_real_system_only_returns_own_processes(self):
        for proc in ProcessSampler()._visible():
            try:
                self.assertEqual(proc.uids().real, self.me)
            except psutil.Error:
                continue  # process vanished while checking

    def test_no_all_users_cli_flag(self):
        from whosup.cli import build_parser
        self.assertNotIn("all-users", build_parser().format_help())


class ProcessDataShapeTests(unittest.TestCase):
    def test_no_sensitive_fields_in_process_models(self):
        for model in (ProcessUsage, ProcessObservation, Finding, ProcessSummary):
            names = {f.name for f in dataclasses.fields(model)}
            self.assertFalse(names & FORBIDDEN_FIELDS, f"{model.__name__}: {names & FORBIDDEN_FIELDS}")

    def test_sampler_never_reads_cmdline_cwd_environ(self):
        class Strict(FakeProc):
            def cmdline(self): raise AssertionError("cmdline read")
            def cwd(self): raise AssertionError("cwd read")
            def environ(self): raise AssertionError("environ read")
            def exe(self): raise AssertionError("exe read")
            def open_files(self): raise AssertionError("open_files read")
        uid = os.getuid() if POSIX else 0
        procs = [Strict(1, "p", uid)]
        with mock.patch("whosup.processes.psutil.process_iter", return_value=procs), \
             mock.patch("whosup.processes.is_current_user", return_value=True):
            ProcessSampler().prime()
            self.assertEqual(ProcessSampler().collect().total_count, 1)


class PossiblyUnexpectedTests(unittest.TestCase):
    def obs(self, cpu=1.0, age=10_000.0, hot=0.0):
        return ProcessObservation("proc", cpu, 1024, age, hot)

    def test_moderate_cpu_is_never_flagged(self):
        self.assertIsNone(rule_new_and_busy(self.obs(cpu=20, age=5)))
        self.assertIsNone(rule_sustained_high_cpu(self.obs(cpu=20, hot=0)))
        self.assertEqual(find_possibly_unexpected([self.obs(cpu=20, age=5)]), [])

    def test_new_and_busy(self):
        finding = rule_new_and_busy(self.obs(cpu=HIGH_CPU_PERCENT + 5, age=NEW_PROCESS_SECONDS - 1))
        self.assertIsNotNone(finding)
        self.assertIsNone(rule_new_and_busy(self.obs(cpu=99, age=NEW_PROCESS_SECONDS + 1)))

    def test_sustained(self):
        self.assertIsNotNone(rule_sustained_high_cpu(self.obs(cpu=95, hot=SUSTAINED_SECONDS)))
        self.assertIsNone(rule_sustained_high_cpu(self.obs(cpu=95, hot=SUSTAINED_SECONDS - 1)))

    def test_one_finding_per_process_and_safe_wording(self):
        both = self.obs(cpu=99, age=30, hot=500)
        findings = find_possibly_unexpected([both])
        self.assertEqual(len(findings), 1)
        for finding in findings:
            for word in FORBIDDEN_WORDS:
                self.assertNotIn(word, finding.reason.lower())

    def test_broken_rule_is_ignored(self):
        def broken(obs): raise RuntimeError("boom")
        self.assertEqual(find_possibly_unexpected([self.obs(cpu=99, age=1)], rules=[broken]), [])

    def test_rules_get_observations_only(self):
        self.assertTrue(RULES)
        fields = {f.name for f in dataclasses.fields(ProcessObservation)}
        self.assertEqual(fields, {"name", "cpu_percent", "ram_bytes", "age_seconds", "high_cpu_seconds"})

    @unittest.skipUnless(POSIX, "uid filtering is POSIX-specific")
    def test_sampler_tracks_sustained_cpu(self):
        uid = os.getuid()
        busy = FakeProc(1, "busy", uid, cpu=psutil.cpu_count() * 95.0)
        sampler = ProcessSampler()
        clock = [1000.0]
        with mock.patch("whosup.processes.psutil.process_iter", return_value=[busy]), \
             mock.patch("whosup.processes.time.monotonic", side_effect=lambda: clock[0]), \
             mock.patch("whosup.processes.os.getpid", return_value=-1):
            self.assertEqual(sampler.collect().unexpected, [])
            clock[0] += SUSTAINED_SECONDS + 5
            flagged = sampler.collect().unexpected
        self.assertEqual([f.name for f in flagged], ["busy"])

    @unittest.skipUnless(POSIX, "UID filtering is POSIX-specific")
    def test_process_count_excludes_other_users(self):
        import os
        uid = os.getuid()
        mine = FakeProc(1, "mine", uid)
        other = FakeProc(2, "other", uid + 1)
        sampler = ProcessSampler()
        with mock.patch("whosup.processes.psutil.process_iter", return_value=[mine, other]):
            summary = sampler.collect()
        self.assertEqual(summary.total_count, 1)
        self.assertEqual([p.name for p in summary.top], ["mine"])


if __name__ == "__main__":
    unittest.main()
