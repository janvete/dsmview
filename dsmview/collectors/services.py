from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from dsmview.collectors.base import Collector


@dataclass(slots=True)
class ServiceInfo:
    name: str
    running: bool = False
    description: str = ""


@dataclass(slots=True)
class ServicesSnapshot:
    services: List[ServiceInfo] = field(default_factory=list)


# Names worth surfacing in the compact dashboard view.
INTERESTING = {
    "smbd", "smb", "nmbd", "nginx", "sshd", "nfsd", "ftpd",
    "avahi-daemon", "crond", "chronyd", "synoindexd", "findhostd",
    "synocachefs", "synonetd", "synopkg", "synowebapi",
    "pgsql", "synologdbd",
}


class ServicesCollector(Collector[ServicesSnapshot]):
    """Lists systemd services with running status.

    Synology DSM 7.x uses systemd. Older `synoservicectl` / `synosystemctl`
    are absent on recent DSM builds, so we go straight to `systemctl`.
    """

    name = "services"

    async def collect(self) -> ServicesSnapshot:
        # --no-legend keeps the table machine-parseable; --plain removes
        # the unicode tree characters that some systemd versions emit.
        result = await self.executor.run(
            "systemctl list-units --type=service --all --no-legend --no-pager --plain 2>/dev/null || true",
            timeout=10.0,
        )
        services = self._parse(result.stdout)
        return ServicesSnapshot(services=services)

    @staticmethod
    def _parse(text: str) -> List[ServiceInfo]:
        out: List[ServiceInfo] = []
        for line in text.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            unit = parts[0]
            # systemctl marks failed/loaded/not-found in column 2; we want
            # the SUB state in column 4 (running/dead/exited/etc).
            sub_state = parts[3]
            desc = parts[4] if len(parts) > 4 else ""
            if not unit.endswith(".service"):
                continue
            name = unit[: -len(".service")]
            # Strip pkg- prefix DSM uses for package-installed services so
            # smbd shows as smbd, not pkg-smbd.
            display = name[4:] if name.startswith("pkg-") else name
            running = sub_state == "running"
            out.append(ServiceInfo(name=display, running=running, description=desc.strip().strip('"')))
        # Sort: interesting services first, then running ones, then the rest.
        def sort_key(s: ServiceInfo) -> tuple:
            interesting = 0 if s.name in INTERESTING else 1
            running = 0 if s.running else 1
            return (interesting, running, s.name)
        out.sort(key=sort_key)
        return out
