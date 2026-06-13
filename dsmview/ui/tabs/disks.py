from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Static

from dsmview.collectors.disks import DisksSnapshot
from dsmview.collectors.storage import StorageSnapshot
from dsmview.ui import theme


class DisksTab(Container):
    def compose(self) -> ComposeResult:
        with Container(classes="panel"):
            yield Static("DISKS", classes="panel-title")
            self.disks_table = DataTable(zebra_stripes=False)
            self.disks_table.add_columns(
                "DISK", "MODEL", "SIZE", "TEMP", "HEALTH", "REALLOC", "PENDING", "UNCORR",
            )
            yield self.disks_table
            yield Static("RAID", classes="panel-title")
            self.raid_view = Static("")
            yield self.raid_view

    def update_disks(self, snap: DisksSnapshot) -> None:
        self.disks_table.clear()
        for d in snap.disks:
            temp = f"{d.temperature_c}°C" if d.temperature_c is not None else "—"
            health_color = (
                theme.OK if d.smart_ok is True
                else theme.CRITICAL if d.smart_ok is False
                else theme.WARNING
            )
            health = f"[{health_color}]{d.health}[/]"
            self.disks_table.add_row(
                d.device, d.model or "—", d.size or "—", temp, health,
                str(d.reallocated) if d.reallocated is not None else "—",
                str(d.pending) if d.pending is not None else "—",
                str(d.uncorrectable) if d.uncorrectable is not None else "—",
            )

    def update_raid(self, snap: StorageSnapshot) -> None:
        if not snap.raids:
            self.raid_view.update("(no RAID arrays detected)")
            return
        lines = []
        for r in snap.raids:
            lines.append(f"{r.name:<10} {r.level:<8} {r.state}   devices: {', '.join(r.devices) or '—'}")
        self.raid_view.update("\n".join(lines))
