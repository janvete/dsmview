from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from dsmview.collectors.base import Collector

_SIZE_RE = re.compile(r"User Capacity:\s+[\d,]+\s+bytes\s+\[(?P<size>[^\]]+)\]")
_MODEL_RE = re.compile(r"Device Model:\s+(?P<model>.+)")
_VENDOR_RE = re.compile(r"Vendor:\s+(?P<vendor>\S+)")
_PRODUCT_RE = re.compile(r"Product:\s+(?P<product>.+)")
_TEMP_RE = re.compile(
    r"(?:Temperature_Celsius|Airflow_Temperature_Cel)\s+\S+\s+\d+\s+\d+\s+\d+\s+\S+\s+\S+\s+\S+\s+(\d+)"
)
_HEALTH_RE = re.compile(r"SMART overall-health self-assessment test result:\s+(\S+)")
_REALLOC_RE = re.compile(r"Reallocated_Sector_Ct\s+.*?\s(\d+)(?:\s|$)", re.MULTILINE)
_PENDING_RE = re.compile(r"Current_Pending_Sector\s+.*?\s(\d+)(?:\s|$)", re.MULTILINE)
_UNCORR_RE = re.compile(r"Offline_Uncorrectable\s+.*?\s(\d+)(?:\s|$)", re.MULTILINE)


@dataclass(slots=True)
class DiskInfo:
    device: str
    model: str = ""
    size: str = ""
    temperature_c: Optional[int] = None
    health: str = "N/A"
    smart_ok: Optional[bool] = None
    reallocated: Optional[int] = None
    pending: Optional[int] = None
    uncorrectable: Optional[int] = None


@dataclass(slots=True)
class DisksSnapshot:
    disks: List[DiskInfo] = field(default_factory=list)


class DisksCollector(Collector[DisksSnapshot]):
    name = "disks"

    async def collect(self) -> DisksSnapshot:
        # Synology exposes drives as /dev/sata{N} (newer models) or
        # /dev/sd{a..z} (older). NVMe cache may be /dev/nvme{N}n1.
        # List top-level devices only (no partitions like sata1p1).
        listing = await self.executor.run(
            "ls -d /dev/sata[0-9] /dev/sata[1-9][0-9] /dev/sd[a-z] /dev/nvme[0-9]n1 2>/dev/null"
        )
        devices: List[str] = []
        for line in listing.stdout.split():
            line = line.strip()
            if line.startswith("/dev/") and "p" not in line.rsplit("/", 1)[-1]:
                devices.append(line)

        snap = DisksSnapshot()
        if not devices:
            return snap

        # `-d sat` is needed on Synology because drives are presented via a
        # SCSI shim. Without it, smartctl reports "SMART unavailable".
        smart_cmds = [f"smartctl -a -d sat {d} 2>&1 || smartctl -a {d} 2>&1 || true" for d in devices]
        health_cmds = [f"smartctl -H -d sat {d} 2>&1 || smartctl -H {d} 2>&1 || true" for d in devices]
        smart_results = await self.executor.gather(smart_cmds, timeout=20.0)
        health_results = await self.executor.gather(health_cmds, timeout=10.0)

        for device, smart, health in zip(devices, smart_results, health_results):
            info = DiskInfo(device=device)
            self._parse_smart(smart.stdout, info)
            self._parse_health(health.stdout, info)
            snap.disks.append(info)
        return snap

    @staticmethod
    def _parse_smart(text: str, info: DiskInfo) -> None:
        if not text:
            return
        m = _MODEL_RE.search(text)
        if m:
            info.model = m.group("model").strip()
        else:
            # Enterprise drives often report as SCSI (Vendor:/Product:).
            vendor = _VENDOR_RE.search(text)
            product = _PRODUCT_RE.search(text)
            if vendor and product:
                info.model = f"{vendor.group('vendor').strip()} {product.group('product').strip()}"
        m = _SIZE_RE.search(text)
        if m:
            info.size = m.group("size").strip()
        m = _TEMP_RE.search(text)
        if m:
            try:
                info.temperature_c = int(m.group(1))
            except ValueError:
                pass
        m = _REALLOC_RE.search(text)
        if m:
            info.reallocated = int(m.group(1))
        m = _PENDING_RE.search(text)
        if m:
            info.pending = int(m.group(1))
        m = _UNCORR_RE.search(text)
        if m:
            info.uncorrectable = int(m.group(1))

    @staticmethod
    def _parse_health(text: str, info: DiskInfo) -> None:
        m = _HEALTH_RE.search(text)
        if m:
            info.health = m.group(1).strip()
            info.smart_ok = info.health.upper() in ("PASSED", "OK")
