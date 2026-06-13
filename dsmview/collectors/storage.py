from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from dsmview.collectors.base import Collector

_VOLUME_RE = re.compile(r"^/volume\d+$")


@dataclass(slots=True)
class VolumeInfo:
    device: str
    mount: str
    size: str
    used: str
    avail: str
    percent: float


@dataclass(slots=True)
class RaidInfo:
    name: str
    level: str
    state: str
    devices: List[str] = field(default_factory=list)


@dataclass(slots=True)
class StorageSnapshot:
    volumes: List[VolumeInfo] = field(default_factory=list)
    raids: List[RaidInfo] = field(default_factory=list)


class StorageCollector(Collector[StorageSnapshot]):
    name = "storage"

    async def collect(self) -> StorageSnapshot:
        df, mdstat = await self.executor.gather([
            "df -hP",
            "cat /proc/mdstat",
        ])
        snap = StorageSnapshot()
        snap.volumes = self._parse_df(df.stdout)
        snap.raids = self._parse_mdstat(mdstat.stdout)
        return snap

    @staticmethod
    def _parse_df(text: str) -> List[VolumeInfo]:
        out: List[VolumeInfo] = []
        for line in text.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 6:
                continue
            device, size, used, avail, pct, mount = parts[:6]
            # Only show actual storage pools — /volume1, /volume2, etc.
            # Container Manager bind-mounts (/volume1/@appdata/...) and
            # system mounts repeat the same usage and just add noise.
            if not _VOLUME_RE.match(mount):
                continue
            if device in ("tmpfs", "devtmpfs", "overlay", "none"):
                continue
            try:
                p = float(pct.rstrip("%"))
            except ValueError:
                p = 0.0
            out.append(VolumeInfo(
                device=device, mount=mount,
                size=size, used=used, avail=avail, percent=p,
            ))
        return out

    @staticmethod
    def _parse_mdstat(text: str) -> List[RaidInfo]:
        raids: List[RaidInfo] = []
        current: RaidInfo | None = None
        for line in text.splitlines():
            line = line.rstrip()
            if line.startswith("md"):
                head = line.split()
                if len(head) < 4:
                    continue
                name = head[0]
                state = head[2]
                level = head[3] if len(head) > 3 else ""
                devices = [d.split("[")[0] for d in head[4:]]
                current = RaidInfo(name=name, level=level, state=state, devices=devices)
                raids.append(current)
            elif current is not None and ("[" in line and "_" in line or "U" in line):
                stripped = line.strip()
                if stripped.startswith("[") and "]" in stripped:
                    current.state = f"{current.state} {stripped}"
        return raids
