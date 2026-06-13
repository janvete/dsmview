from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dsmview.collectors.base import Collector

# Interface prefixes we never want to surface — virtual, internal,
# bridge, container, VPN.
_HIDE_PREFIXES = (
    "lo", "docker", "veth", "br-", "virbr", "tap", "tun",
    "sit", "ovs-system", "dummy", "wg",
)
# Open vSwitch on Synology exposes the real NIC twice — as `ethN` and
# `ovs_ethN`. The ovs_ wrapper is the one with the IP, so prefer it.
_OVS_RE = re.compile(r"^ovs_(eth\d+)$")


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
    ip: str = ""


@dataclass(slots=True)
class NetworkSnapshot:
    samples: List[NetSample] = field(default_factory=list)

    def primary(self) -> Optional[NetSample]:
        """Pick the interface with the most accumulated traffic. Falls
        back to the first sample if no counters have moved yet."""
        if not self.samples:
            return None
        with_traffic = [s for s in self.samples if (s.rx_total + s.tx_total) > 0]
        if with_traffic:
            return max(with_traffic, key=lambda s: s.rx_total + s.tx_total)
        return self.samples[0]


class NetworkCollector(Collector[NetworkSnapshot]):
    name = "network"

    def __init__(self, executor) -> None:
        super().__init__(executor)
        self._prev: Dict[str, IfaceCounters] = {}

    async def collect(self) -> NetworkSnapshot:
        netdev, ipaddr = await self.executor.gather([
            "cat /proc/net/dev",
            "ip -o -4 addr show 2>/dev/null || true",
        ])
        ips = self._parse_ip_addrs(ipaddr.stdout)
        return self._merge(netdev.stdout, ips)

    @staticmethod
    def _parse_ip_addrs(text: str) -> Dict[str, str]:
        """Map interface name → first IPv4 address."""
        out: Dict[str, str] = {}
        for line in text.splitlines():
            parts = line.split()
            if len(parts) < 4 or parts[2] != "inet":
                continue
            iface = parts[1]
            cidr = parts[3]
            addr = cidr.split("/", 1)[0]
            out.setdefault(iface, addr)
        return out

    def _merge(self, netdev_text: str, ips: Dict[str, str]) -> NetworkSnapshot:
        snap = NetworkSnapshot()
        now = time.monotonic()
        # First pass: read counters for all visible non-hidden interfaces.
        candidates: Dict[str, NetSample] = {}
        for line in netdev_text.splitlines():
            if ":" not in line:
                continue
            name, _, rest = line.partition(":")
            iface = name.strip()
            if self._is_hidden(iface):
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
            sample = NetSample(iface=iface, rx_total=rx, tx_total=tx, ip=ips.get(iface, ""))
            if prev is not None:
                dt = current.timestamp - prev.timestamp
                if dt > 0:
                    sample.rx_bps = max(0.0, (rx - prev.rx_bytes) / dt)
                    sample.tx_bps = max(0.0, (tx - prev.tx_bytes) / dt)
            candidates[iface] = sample
            self._prev[iface] = current

        # OvS hides the real NIC behind both `ethN` and `ovs_ethN`. The
        # ovs_ entry is what carries the IP; drop the raw ethN twin when
        # both exist so we don't show a duplicate row.
        for name in list(candidates):
            m = _OVS_RE.match(name)
            if m and m.group(1) in candidates:
                candidates.pop(m.group(1), None)

        # Sort: interfaces with an IP first, then by total traffic desc.
        snap.samples = sorted(
            candidates.values(),
            key=lambda s: (0 if s.ip else 1, -(s.rx_total + s.tx_total), s.iface),
        )
        return snap

    @staticmethod
    def _is_hidden(iface: str) -> bool:
        for prefix in _HIDE_PREFIXES:
            if iface == prefix or iface.startswith(prefix):
                return True
        return False
