from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from dsmview.collectors.base import Collector

_STATUS_RE = re.compile(r"\b(is\s+running|is\s+stopped|start/running|stop/waiting)\b", re.IGNORECASE)


@dataclass(slots=True)
class ServiceInfo:
    name: str
    running: bool = False
    status_text: str = ""


@dataclass(slots=True)
class ServicesSnapshot:
    services: List[ServiceInfo] = field(default_factory=list)


class ServicesCollector(Collector[ServicesSnapshot]):
    name = "services"

    DEFAULT_SERVICES = (
        "smbd", "nmbd", "nginx", "sshd", "nfsd", "ftpd",
        "avahi-daemon", "crond", "synoindexd",
        "pkgctl-HyperBackup", "pkgctl-ActiveBackup", "pkgctl-CloudSync",
        "pkgctl-MariaDB10", "pkgctl-ContainerManager",
    )

    async def collect(self) -> ServicesSnapshot:
        listing = await self.executor.run("synoservicectl --list 2>/dev/null || true")
        names = self._parse_list(listing.stdout)
        if not names:
            names = list(self.DEFAULT_SERVICES)

        cmds = [f"synoservicectl --status {n} 2>&1 || true" for n in names]
        results = await self.executor.gather(cmds, timeout=15.0)
        snap = ServicesSnapshot()
        for name, res in zip(names, results):
            info = ServiceInfo(name=name, status_text=res.stdout.strip())
            running = self._is_running(res.stdout)
            info.running = running
            snap.services.append(info)
        return snap

    @staticmethod
    def _parse_list(text: str) -> List[str]:
        out: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for token in line.split():
                if token and token[0].isalpha() and "/" not in token:
                    out.append(token)
        seen: dict[str, None] = {}
        for n in out:
            seen[n] = None
        return list(seen.keys())

    @staticmethod
    def _is_running(text: str) -> bool:
        low = text.lower()
        if "is running" in low or "start/running" in low:
            return True
        if "is stopped" in low or "stop/waiting" in low:
            return False
        return "running" in low and "not" not in low
