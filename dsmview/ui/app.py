from __future__ import annotations

import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static, TabbedContent, TabPane

from dsmview.collectors import (
    DisksCollector,
    LogCollector,
    NetworkCollector,
    ServicesCollector,
    StorageCollector,
    SystemCollector,
)
from dsmview.ssh.connection import NasConnection
from dsmview.ssh.executor import Executor
from dsmview.ui import theme
from dsmview.ui.tabs import DashboardTab, LogsTab


# Three refresh tiers — fast for live metrics, medium for storage/services,
# slow for SMART (smartctl is heavy and runs per disk).
REFRESH_FAST = 1.0
REFRESH_MED = 5.0
REFRESH_SLOW = 30.0


class DsmviewApp(App):
    CSS = theme.CSS
    TITLE = "dsmview"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_now", "Refresh"),
        Binding("f1", "switch_tab('dashboard')", "Dash"),
        Binding("f2", "switch_tab('logs')", "Logs"),
        Binding("a", "filter('ALL')", "All", show=False),
        Binding("1", "filter('ERROR')", "Err", show=False),
        Binding("2", "filter('WARN')", "Warn", show=False),
        Binding("3", "filter('SECURITY')", "Sec", show=False),
        Binding("4", "filter('INFO')", "Info", show=False),
    ]

    def __init__(self, connection: NasConnection) -> None:
        super().__init__()
        self.connection = connection
        self.executor = Executor(connection, max_workers=8)
        self.system = SystemCollector(self.executor)
        self.storage = StorageCollector(self.executor)
        self.disks = DisksCollector(self.executor)
        self.network = NetworkCollector(self.executor)
        self.logs = LogCollector(self.executor)
        self.services = ServicesCollector(self.executor)
        self._dsm_label: str = "—"
        self._tail_workers: list = []

    def compose(self) -> ComposeResult:
        self.topbar = Static("", id="topbar")
        yield self.topbar
        with TabbedContent(initial="dashboard"):
            with TabPane("F1 Dashboard", id="dashboard"):
                self.dashboard = DashboardTab()
                yield self.dashboard
            with TabPane("F2 Logs", id="logs"):
                self.logs_tab = LogsTab()
                yield self.logs_tab
        yield Footer()

    def on_mount(self) -> None:
        self._update_topbar()
        self.set_interval(REFRESH_FAST, self._tick_fast)
        self.set_interval(REFRESH_MED, self._tick_medium)
        self.set_interval(REFRESH_SLOW, self._tick_slow)
        self.set_interval(1.0, self._update_topbar)
        self.action_refresh_now()
        self._start_log_tails()

    def on_unmount(self) -> None:
        for w in self._tail_workers:
            try:
                w.cancel()
            except Exception:
                pass
        self.executor.close()
        self.connection.close()

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id

    def action_filter(self, name: str) -> None:
        self.query_one(TabbedContent).active = "logs"
        self.logs_tab.set_filter(name)

    def action_refresh_now(self) -> None:
        self._tick_fast()
        self._tick_medium()
        self._tick_slow()

    def _tick_fast(self) -> None:
        self.run_worker(self._refresh_fast(), exclusive=True, group="refresh-fast")

    def _tick_medium(self) -> None:
        self.run_worker(self._refresh_medium(), exclusive=True, group="refresh-med")

    def _tick_slow(self) -> None:
        self.run_worker(self._refresh_slow(), exclusive=True, group="refresh-slow")

    async def _refresh_fast(self) -> None:
        try:
            system_snap, net_snap = await asyncio.gather(
                self.system.collect(),
                self.network.collect(),
            )
        except Exception as e:
            self.notify(f"fast refresh error: {e}", severity="error", timeout=4)
            return
        self.dashboard.update_system(system_snap)
        self.dashboard.update_network(net_snap)
        if self._dsm_label == "—":
            self._dsm_label = self._make_dsm_label(system_snap)

    async def _refresh_medium(self) -> None:
        try:
            storage_snap, services_snap = await asyncio.gather(
                self.storage.collect(),
                self.services.collect(),
            )
        except Exception as e:
            self.notify(f"storage/services error: {e}", severity="warning", timeout=4)
            return
        self.dashboard.update_storage(storage_snap)
        self.dashboard.update_services(services_snap.services)

    async def _refresh_slow(self) -> None:
        try:
            disks_snap = await self.disks.collect()
        except Exception as e:
            self.notify(f"disks error: {e}", severity="warning", timeout=4)
            return
        self.dashboard.update_disks(disks_snap)

    def _start_log_tails(self) -> None:
        self.run_worker(self._tail_logs_initial(), group="logs-init", exclusive=True)
        for i in range(len(self.logs.SOURCES)):
            w = self.run_worker(self._tail_logs(i), group=f"tail-{i}", exclusive=False)
            self._tail_workers.append(w)

    async def _tail_logs_initial(self) -> None:
        try:
            initial = await self.logs.collect()
            self.logs_tab.push_initial(initial)
        except Exception as e:
            self.notify(f"log fetch error: {e}", severity="warning", timeout=4)

    async def _tail_logs(self, source_index: int) -> None:
        try:
            async for line in self.logs.tail(source_index):
                self.logs_tab.push(line)
        except Exception:
            return

    def _update_topbar(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        target = self.connection.target.label
        self.topbar.update(
            f"[bold]dsmview[/]  │  {target}  │  {self._dsm_label}  │  {now}"
        )

    @staticmethod
    def _make_dsm_label(s) -> str:
        parts = []
        if s.dsm_model:
            parts.append(s.dsm_model)
        if s.dsm_version:
            parts.append(f"DSM {s.dsm_version}")
        if s.hostname:
            parts.append(s.hostname)
        return " ".join(parts) if parts else "—"
