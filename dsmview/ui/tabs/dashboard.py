from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static

from dsmview.collectors.network import NetworkSnapshot
from dsmview.collectors.storage import StorageSnapshot
from dsmview.collectors.system import SystemSnapshot
from dsmview.ui import theme
from dsmview.ui.widgets import BrailleGraph, MeterBar


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


class DashboardTab(Container):
    def compose(self) -> ComposeResult:
        with Container(id="dashboard-grid"):
            with Vertical(id="cpu-panel", classes="panel"):
                yield Static("CPU", classes="panel-title")
                self.cpu_meter = MeterBar("CPU", color=theme.CPU_BAR)
                self.cpu_meter.add_class("meter-cpu")
                yield self.cpu_meter
                self.cpu_graph = BrailleGraph(color="red", y_max=100.0)
                yield self.cpu_graph
                self.cpu_summary = Static("", id="cpu-summary")
                yield self.cpu_summary

            with Vertical(id="storage-panel", classes="panel"):
                yield Static("STORAGE", classes="panel-title")
                self.storage_body = Static("")
                yield self.storage_body

            with Vertical(id="mem-panel", classes="panel"):
                yield Static("MEMORY", classes="panel-title")
                self.mem_meter = MeterBar("MEM", color=theme.MEM_BAR)
                self.mem_meter.add_class("meter-mem")
                yield self.mem_meter
                self.mem_summary = Static("", id="mem-summary")
                yield self.mem_summary

            with Vertical(id="net-panel", classes="panel"):
                yield Static("NETWORK", classes="panel-title")
                self.net_summary = Static("")
                yield self.net_summary
                with Horizontal():
                    self.net_rx_graph = BrailleGraph(color="magenta")
                    self.net_tx_graph = BrailleGraph(color="blue")
                    yield self.net_rx_graph
                    yield self.net_tx_graph

    def update_system(self, s: SystemSnapshot) -> None:
        self.cpu_meter.update(s.cpu_percent)
        self.cpu_graph.push(s.cpu_percent)
        temp = f"  temp {s.temperature_c:.0f}°C" if s.temperature_c is not None else ""
        self.cpu_summary.update(
            f"load {s.load_1:.2f} {s.load_5:.2f} {s.load_15:.2f}   "
            f"cores {s.cpu_count}   up {_fmt_uptime(s.uptime_seconds)}{temp}"
        )
        self.mem_meter.update(s.mem_percent)
        used_mb = s.mem_used_kb / 1024
        total_mb = s.mem_total_kb / 1024
        cached_mb = s.mem_cached_kb / 1024
        self.mem_summary.update(
            f"used {used_mb:7.0f} MiB / total {total_mb:7.0f} MiB   cached {cached_mb:6.0f} MiB"
        )

    def update_storage(self, s: StorageSnapshot) -> None:
        lines = []
        for v in s.volumes:
            bar_w = 20
            filled = int(round(bar_w * v.percent / 100.0))
            color = (
                theme.CRITICAL if v.percent >= 90
                else theme.WARNING if v.percent >= 75
                else theme.DISK_BAR
            )
            bar = f"[{color}]" + "█" * filled + "[/]" + "░" * (bar_w - filled)
            lines.append(
                f"{v.mount:<14} {v.used:>6}/{v.size:>6}  {bar}  {v.percent:5.1f}%"
            )
        if not lines:
            lines.append("(no volumes detected)")
        for r in s.raids:
            lines.append(f"  RAID {r.name} {r.level} {r.state}")
        self.storage_body.update("\n".join(lines))

    def update_network(self, s: NetworkSnapshot) -> None:
        primary = s.primary()
        if primary is None:
            self.net_summary.update("(no interface)")
            return
        self.net_rx_graph.push(primary.rx_bps)
        self.net_tx_graph.push(primary.tx_bps)
        self.net_summary.update(
            f"{primary.iface}   "
            f"[{theme.NET_DOWN}]↓ {_fmt_bytes_per_sec(primary.rx_bps)}[/]   "
            f"[{theme.NET_UP}]↑ {_fmt_bytes_per_sec(primary.tx_bps)}[/]"
        )
