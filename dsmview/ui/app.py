from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
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
from dsmview.ui.tabs import DashboardTab, DisksTab, LogsTab, ServicesTab


REFRESH_INTERVAL = 10.0


class ConfirmDialog(ModalScreen[bool]):
    """Y/N confirmation modal for destructive actions."""

    BINDINGS = [
        Binding("y", "confirm(True)", "Yes", show=False),
        Binding("n", "confirm(False)", "No", show=False),
        Binding("escape", "confirm(False)", "Cancel", show=False),
    ]

    def __init__(self, action: str, service: str, host: str) -> None:
        super().__init__()
        self.action = action
        self.service = service
        self.host = host

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Static(f"⚠️  CONFIRM", id="dialog-title")
            yield Static(f"{self.action.title()} service: [bold]{self.service}[/]")
            yield Static(f"on: {self.host}")
            yield Static("")
            yield Static("[Y] Potvrdit    [N] Zrušit")

    def action_confirm(self, ok: bool) -> None:
        self.dismiss(ok)


class DsmviewApp(App):
    CSS = theme.CSS
    TITLE = "dsmview"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_now", "Refresh"),
        Binding("f1", "switch_tab('dashboard')", "Dash"),
        Binding("f2", "switch_tab('logs')", "Logs"),
        Binding("f3", "switch_tab('services')", "Services"),
        Binding("f4", "switch_tab('disks')", "Disks"),
    ]

    def __init__(self, connection: NasConnection) -> None:
        super().__init__()
        self.connection = connection
        self.executor = Executor(connection, max_workers=6)
        self.system = SystemCollector(self.executor)
        self.storage = StorageCollector(self.executor)
        self.disks = DisksCollector(self.executor)
        self.network = NetworkCollector(self.executor)
        self.logs = LogCollector(self.executor)
        self.services = ServicesCollector(self.executor)
        self._dsm_label: str = "—"
        self._refresh_lock = asyncio.Lock()
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
            with TabPane("F3 Services", id="services"):
                self.services_tab = ServicesTab(on_action=self._handle_service_action)
                yield self.services_tab
            with TabPane("F4 Disks", id="disks"):
                self.disks_tab = DisksTab()
                yield self.disks_tab
        yield Footer()

    def on_mount(self) -> None:
        self._update_topbar()
        self.set_interval(REFRESH_INTERVAL, self.action_refresh_now)
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
        tabbed = self.query_one(TabbedContent)
        tabbed.active = tab_id

    def action_refresh_now(self) -> None:
        self.run_worker(self._refresh_all(), exclusive=True, group="refresh")

    async def _refresh_all(self) -> None:
        async with self._refresh_lock:
            try:
                system_task = asyncio.create_task(self.system.collect())
                storage_task = asyncio.create_task(self.storage.collect())
                network_task = asyncio.create_task(self.network.collect())
                services_task = asyncio.create_task(self.services.collect())
                disks_task = asyncio.create_task(self.disks.collect())

                system_snap = await system_task
                storage_snap = await storage_task
                net_snap = await network_task
                services_snap = await services_task
                disks_snap = await disks_task
            except Exception as e:
                self.notify(f"Refresh error: {e}", severity="error", timeout=5)
                return

            if not self._dsm_label or self._dsm_label == "—":
                self._dsm_label = self._make_dsm_label(system_snap)
                self._update_topbar()

            self.dashboard.update_system(system_snap)
            self.dashboard.update_storage(storage_snap)
            self.dashboard.update_network(net_snap)
            self.services_tab.update_services(services_snap.services)
            self.disks_tab.update_disks(disks_snap)
            self.disks_tab.update_raid(storage_snap)

    def _start_log_tails(self) -> None:
        self.run_worker(self._tail_logs_initial(), group="logs-init", exclusive=True)
        for i, (path, source) in enumerate(self.logs.SOURCES):
            w = self.run_worker(self._tail_logs(i), group=f"tail-{i}", exclusive=False)
            self._tail_workers.append(w)

    async def _tail_logs_initial(self) -> None:
        try:
            initial = await self.logs.collect()
            self.logs_tab.push_initial(initial)
        except Exception as e:
            self.notify(f"Log fetch error: {e}", severity="warning", timeout=4)

    async def _tail_logs(self, source_index: int) -> None:
        try:
            async for line in self.logs.tail(source_index):
                self.logs_tab.push(line)
        except Exception:
            return

    def _handle_service_action(self, action: str, name: str) -> None:
        def on_result(ok: bool | None) -> None:
            if ok:
                self.run_worker(self._run_service_action(action, name), exclusive=False, group="svc")

        self.push_screen(
            ConfirmDialog(action, name, self.connection.target.label),
            on_result,
        )

    async def _run_service_action(self, action: str, name: str) -> None:
        flag = {"restart": "--restart", "stop": "--stop", "start": "--start"}[action]
        result = await self.executor.run(f"synoservicectl {flag} {name}")
        if result.ok:
            self.notify(f"{action} {name}: OK")
        else:
            self.notify(f"{action} {name} failed: {result.stderr or result.stdout}", severity="error")
        await self._refresh_all()

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
