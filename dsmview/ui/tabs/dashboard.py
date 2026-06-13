from __future__ import annotations

from typing import Iterable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Static

from dsmview.collectors.disks import DisksSnapshot
from dsmview.collectors.network import NetworkSnapshot
from dsmview.collectors.services import ServiceInfo
from dsmview.collectors.storage import StorageSnapshot
from dsmview.collectors.system import SystemSnapshot
from dsmview.ui import theme
from dsmview.ui.widgets import BrailleGraph


def _fmt_bytes_per_sec(b: float) -> str:
    units = ("B/s", "K/s", "M/s", "G/s")
    i = 0
    while b >= 1024 and i < len(units) - 1:
        b /= 1024
        i += 1
    return f"{b:6.1f} {units[i]}"


def _fmt_uptime(s: float) -> str:
    s = int(s)
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, _ = divmod(s, 60)
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    return f"{hours:02d}h {minutes:02d}m"


def _inline_bar(percent: float, width: int, color: str) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * percent / 100.0))
    return f"[{color}]" + "█" * filled + "[/]" + "░" * (width - filled)


class DashboardTab(VerticalScroll):
    """Single-screen dashboard packing system / storage / network /
    services / disks into one vertically-flowing view."""

    DEFAULT_CSS = """
    DashboardTab {
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        # System (CPU + MEM compact, inline summary + braille graph)
        with Container(classes="panel"):
            yield Static("SYSTEM", classes="panel-title")
            self.cpu_line = Static("")
            yield self.cpu_line
            self.cpu_graph = BrailleGraph(color="red", y_max=100.0)
            self.cpu_graph.styles.height = 4
            yield self.cpu_graph
            self.mem_line = Static("")
            yield self.mem_line

        with Container(classes="panel"):
            yield Static("STORAGE", classes="panel-title")
            self.storage_body = Static("")
            yield self.storage_body

        with Container(classes="panel"):
            yield Static("NETWORK", classes="panel-title")
            self.net_summary = Static("")
            yield self.net_summary
            with Horizontal(id="net-graphs"):
                self.net_rx_graph = BrailleGraph(color="magenta")
                self.net_rx_graph.styles.height = 4
                self.net_tx_graph = BrailleGraph(color="blue")
                self.net_tx_graph.styles.height = 4
                yield self.net_rx_graph
                yield self.net_tx_graph

        with Container(classes="panel"):
            yield Static("SERVICES", classes="panel-title")
            self.services_body = Static("")
            yield self.services_body

        with Container(classes="panel"):
            yield Static("DISKS", classes="panel-title")
            self.disks_table = DataTable(zebra_stripes=False, show_cursor=False)
            self.disks_table.add_columns("DISK", "MODEL", "SIZE", "TEMP", "HEALTH", "REALLOC", "PENDING")
            yield self.disks_table

    def update_system(self, s: SystemSnapshot) -> None:
        bar = _inline_bar(s.cpu_percent, 30, theme.CPU_BAR)
        temp = f"  [grey70]temp[/] {s.temperature_c:.0f}°C" if s.temperature_c is not None else ""
        self.cpu_line.update(
            f"[bold]CPU[/] {s.cpu_percent:5.1f}%  {bar}  "
            f"[grey70]load[/] {s.load_1:.2f}/{s.load_5:.2f}/{s.load_15:.2f}  "
            f"[grey70]{s.cpu_count}c[/]  [grey70]up[/] {_fmt_uptime(s.uptime_seconds)}{temp}"
        )
        self.cpu_graph.push(s.cpu_percent)

        mem_bar = _inline_bar(s.mem_percent, 30, theme.MEM_BAR)
        used_mib = s.mem_used_kb / 1024
        total_mib = s.mem_total_kb / 1024
        cached_mib = s.mem_cached_kb / 1024
        self.mem_line.update(
            f"[bold]MEM[/] {s.mem_percent:5.1f}%  {mem_bar}  "
            f"[grey70]used[/] {used_mib:6.0f} / {total_mib:6.0f} MiB  "
            f"[grey70]cached[/] {cached_mib:5.0f} MiB"
        )

    def update_storage(self, s: StorageSnapshot) -> None:
        lines = []
        for v in s.volumes:
            color = (
                theme.CRITICAL if v.percent >= 90
                else theme.WARNING if v.percent >= 75
                else theme.DISK_BAR
            )
            bar = _inline_bar(v.percent, 24, color)
            lines.append(
                f"  {v.mount:<14} {v.used:>7} / {v.size:>7}  {bar}  {v.percent:5.1f}%"
            )
        if not lines:
            lines.append("  (no volumes detected)")
        if s.raids:
            lines.append("")
            for r in s.raids:
                lines.append(f"  [grey70]RAID[/] {r.name} {r.level:<8} {r.state}")
        self.storage_body.update("\n".join(lines))

    def update_network(self, s: NetworkSnapshot) -> None:
        primary = s.primary()
        if primary is None:
            self.net_summary.update("  (no interface)")
            return
        self.net_rx_graph.push(primary.rx_bps)
        self.net_tx_graph.push(primary.tx_bps)
        # One line per interface so multi-NIC setups (LACP, OvS, Tailscale)
        # are visible. The primary is highlighted because the graph
        # underneath tracks it.
        max_name = max((len(s.iface) for s in s.samples), default=8)
        max_ip = max((len(s.ip) for s in s.samples), default=0)
        lines = []
        for sample in s.samples:
            iface = sample.iface.ljust(max_name)
            ip = (sample.ip or "—").ljust(max_ip if max_ip else 1)
            tag = "[bold]●[/]" if sample is primary else " "
            lines.append(
                f"  {tag} [bold]{iface}[/]  [grey70]{ip}[/]   "
                f"[{theme.NET_DOWN}]↓ {_fmt_bytes_per_sec(sample.rx_bps)}[/]   "
                f"[{theme.NET_UP}]↑ {_fmt_bytes_per_sec(sample.tx_bps)}[/]"
            )
        self.net_summary.update("\n".join(lines))

    SERVICES_LIMIT = 30

    def update_services(self, services: Iterable[ServiceInfo]) -> None:
        items = list(services)
        if not items:
            self.services_body.update("  (no services detected)")
            return
        total = len(items)
        running = sum(1 for s in items if s.running)
        # The collector already sorted interesting+running first, so the
        # head of the list is the most useful.
        shown = items[: self.SERVICES_LIMIT]
        max_name = min(20, max((len(s.name) for s in shown), default=8))
        cells = []
        for s in shown:
            icon = f"[{theme.OK}]✅[/]" if s.running else f"[{theme.STOPPED}]⛔[/]"
            name = (s.name[:max_name]).ljust(max_name)
            cells.append(f"{icon} {name}")
        per_row = 3
        rows = [f"  [dim]({running}/{total} running, showing top {len(shown)})[/]"]
        for i in range(0, len(cells), per_row):
            rows.append("  " + "  ".join(cells[i:i + per_row]))
        self.services_body.update("\n".join(rows))

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
            model = (d.model or "—")[:30]
            self.disks_table.add_row(
                d.device.removeprefix("/dev/"), model, d.size or "—", temp, health,
                str(d.reallocated) if d.reallocated is not None else "—",
                str(d.pending) if d.pending is not None else "—",
            )
