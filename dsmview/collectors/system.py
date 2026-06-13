from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from dsmview.collectors.base import Collector


@dataclass(slots=True)
class CpuTimes:
    total: int = 0
    idle: int = 0

    def diff(self, prev: "CpuTimes") -> float:
        dt = self.total - prev.total
        di = self.idle - prev.idle
        if dt <= 0:
            return 0.0
        return max(0.0, min(100.0, (1.0 - di / dt) * 100.0))


@dataclass(slots=True)
class SystemSnapshot:
    hostname: str = ""
    dsm_model: str = ""
    dsm_version: str = ""
    uptime_seconds: float = 0.0
    load_1: float = 0.0
    load_5: float = 0.0
    load_15: float = 0.0
    cpu_count: int = 0
    cpu_model: str = ""
    cpu_percent: float = 0.0
    cpu_times: CpuTimes = field(default_factory=CpuTimes)
    mem_total_kb: int = 0
    mem_free_kb: int = 0
    mem_available_kb: int = 0
    mem_cached_kb: int = 0
    mem_buffers_kb: int = 0
    temperature_c: Optional[float] = None

    @property
    def mem_used_kb(self) -> int:
        if self.mem_available_kb:
            return max(0, self.mem_total_kb - self.mem_available_kb)
        return max(0, self.mem_total_kb - self.mem_free_kb - self.mem_cached_kb - self.mem_buffers_kb)

    @property
    def mem_percent(self) -> float:
        if not self.mem_total_kb:
            return 0.0
        return self.mem_used_kb / self.mem_total_kb * 100.0


class SystemCollector(Collector[SystemSnapshot]):
    name = "system"

    def __init__(self, executor) -> None:
        super().__init__(executor)
        self._prev_cpu: Optional[CpuTimes] = None

    async def collect(self) -> SystemSnapshot:
        cmds = [
            "cat /proc/loadavg",
            "cat /proc/meminfo",
            "cat /proc/stat",
            "cat /proc/cpuinfo",
            "cat /proc/uptime",
            "cat /proc/sys/kernel/hostname",
            "cat /etc/synoinfo.conf 2>/dev/null | grep -E '^(unique|productversion|buildnumber|upnpmodelname)='",
            "synotemperature 2>/dev/null || true",
        ]
        results = await self.executor.gather(cmds)
        snap = SystemSnapshot()
        self._parse_loadavg(results[0].stdout, snap)
        self._parse_meminfo(results[1].stdout, snap)
        self._parse_stat(results[2].stdout, snap)
        self._parse_cpuinfo(results[3].stdout, snap)
        self._parse_uptime(results[4].stdout, snap)
        snap.hostname = results[5].stdout.strip()
        self._parse_synoinfo(results[6].stdout, snap)
        self._parse_temp(results[7].stdout, snap)
        return snap

    @staticmethod
    def _parse_loadavg(text: str, snap: SystemSnapshot) -> None:
        parts = text.split()
        if len(parts) >= 3:
            try:
                snap.load_1 = float(parts[0])
                snap.load_5 = float(parts[1])
                snap.load_15 = float(parts[2])
            except ValueError:
                pass

    @staticmethod
    def _parse_meminfo(text: str, snap: SystemSnapshot) -> None:
        for line in text.splitlines():
            key, _, rest = line.partition(":")
            value = rest.strip().split()
            if not value:
                continue
            try:
                kb = int(value[0])
            except ValueError:
                continue
            if key == "MemTotal":
                snap.mem_total_kb = kb
            elif key == "MemFree":
                snap.mem_free_kb = kb
            elif key == "MemAvailable":
                snap.mem_available_kb = kb
            elif key == "Cached":
                snap.mem_cached_kb = kb
            elif key == "Buffers":
                snap.mem_buffers_kb = kb

    def _parse_stat(self, text: str, snap: SystemSnapshot) -> None:
        for line in text.splitlines():
            if not line.startswith("cpu "):
                continue
            fields = line.split()
            try:
                values = [int(x) for x in fields[1:]]
            except ValueError:
                return
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
            now = CpuTimes(total=total, idle=idle)
            if self._prev_cpu is not None:
                snap.cpu_percent = now.diff(self._prev_cpu)
            snap.cpu_times = now
            self._prev_cpu = now
            return

    @staticmethod
    def _parse_cpuinfo(text: str, snap: SystemSnapshot) -> None:
        count = 0
        model = ""
        for line in text.splitlines():
            if line.startswith("processor"):
                count += 1
            elif line.startswith("model name") and not model:
                model = line.split(":", 1)[1].strip()
        snap.cpu_count = count
        snap.cpu_model = model

    @staticmethod
    def _parse_uptime(text: str, snap: SystemSnapshot) -> None:
        parts = text.split()
        if parts:
            try:
                snap.uptime_seconds = float(parts[0])
            except ValueError:
                pass

    @staticmethod
    def _parse_synoinfo(text: str, snap: SystemSnapshot) -> None:
        for line in text.splitlines():
            key, _, value = line.partition("=")
            value = value.strip().strip('"')
            if key == "upnpmodelname":
                snap.dsm_model = value
            elif key == "productversion":
                snap.dsm_version = value
            elif key == "buildnumber" and snap.dsm_version:
                snap.dsm_version = f"{snap.dsm_version}-{value}"

    @staticmethod
    def _parse_temp(text: str, snap: SystemSnapshot) -> None:
        text = text.strip()
        if not text:
            return
        for token in text.replace("C", " ").split():
            try:
                snap.temperature_c = float(token)
                return
            except ValueError:
                continue
