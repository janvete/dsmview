from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dsmview.collectors.base import Collector


@dataclass(slots=True)
class IfaceCounters:
    rx_bytes: int = 0
    tx_bytes: int = 0
    timestamp: float = 0.0


@dataclass(slots=True)
class NetSample:
    iface: str
    rx_bps: float = 0.0
    tx_bps: float = 0.0
    rx_total: int = 0
    tx_total: int = 0


@dataclass(slots=True)
class NetworkSnapshot:
    samples: List[NetSample] = field(default_factory=list)

    def primary(self) -> Optional[NetSample]:
        # Pick the interface with the most total traffic. Falls back to
        # eth0-style names when no counters have accumulated yet.
        if not self.samples:
            return None
        with_traffic = [s for s in self.samples if (s.rx_total + s.tx_total) > 0]
        if with_traffic:
            return max(with_traffic, key=lambda s: s.rx_total + s.tx_total)
        for s in self.samples:
            if s.iface in ("eth0", "eth1", "ovs_eth0", "bond0"):
                return s
        return self.samples[0]


class NetworkCollector(Collector[NetworkSnapshot]):
    name = "network"

    def __init__(self, executor) -> None:
        super().__init__(executor)
        self._prev: Dict[str, IfaceCounters] = {}

    async def collect(self) -> NetworkSnapshot:
        result = await self.executor.run("cat /proc/net/dev")
        return self._parse(result.stdout)

    def _parse(self, text: str) -> NetworkSnapshot:
        snap = NetworkSnapshot()
        now = time.monotonic()
        for line in text.splitlines():
            if ":" not in line:
                continue
            name, _, rest = line.partition(":")
            iface = name.strip()
            if iface in ("lo",) or iface.startswith("docker") or iface.startswith("veth"):
                continue
            fields = rest.split()
            if len(fields) < 16:
                continue
            try:
                rx = int(fields[0])
                tx = int(fields[8])
            except ValueError:
                continue
            current = IfaceCounters(rx_bytes=rx, tx_bytes=tx, timestamp=now)
            prev = self._prev.get(iface)
            sample = NetSample(iface=iface, rx_total=rx, tx_total=tx)
            if prev is not None:
                dt = current.timestamp - prev.timestamp
                if dt > 0:
                    sample.rx_bps = max(0.0, (rx - prev.rx_bytes) / dt)
                    sample.tx_bps = max(0.0, (tx - prev.tx_bytes) / dt)
            snap.samples.append(sample)
            self._prev[iface] = current
        return snap
