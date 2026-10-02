"""Fake psutil processes for deterministic privacy tests (test input only)."""

import contextlib
import time
from types import SimpleNamespace

import psutil


class FakeProc:
    def __init__(self, pid, name, uid, rss=1024**2, cpu=0.0, age=1000.0, deny=False):
        self.pid, self._name, self._uid = pid, name, uid
        self._rss, self._cpu, self._created = rss, cpu, time.time() - age
        self._deny = deny

    def uids(self):
        if self._deny:
            raise psutil.AccessDenied(self.pid)
        return SimpleNamespace(real=self._uid, effective=self._uid, saved=self._uid)

    def oneshot(self):
        return contextlib.nullcontext()

    def name(self):
        return self._name

    def memory_info(self):
        return SimpleNamespace(rss=self._rss)

    def cpu_percent(self, interval=None):
        return self._cpu

    def create_time(self):
        return self._created
