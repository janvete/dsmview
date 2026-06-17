from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from dsmview.collectors.services import ServiceInfo
from dsmview.ssh.executor import Executor
from dsmview.ui import theme


class ConfirmActionScreen(ModalScreen[bool]):
    """Tiny modal asking the user to confirm a destructive service action."""

    DEFAULT_CSS = """
    ConfirmActionScreen {
        align: center middle;
    }
    ConfirmActionScreen > Container {
        width: 60;
        height: auto;
        border: round $border;
        background: $surface;
        padding: 1 2;
    }
    ConfirmActionScreen #confirm-title {
        text-style: bold;
        height: auto;
        margin-bottom: 1;
    }
    ConfirmActionScreen #confirm-buttons {
        height: auto;
        align: center middle;
    }
    """

    def __init__(self, action: str, service: str) -> None:
        super().__init__()
        self.action = action
        self.service = service

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(
                f"Confirm {self.action} of [bold]{self.service}[/]?",
                id="confirm-title",
            )
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes", id="confirm-yes", variant="error")
                yield Button("No", id="confirm-no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")


class ServicesTab(Container):
    """Interactive service list with start/stop/restart actions."""

    def __init__(self, executor: Executor) -> None:
        super().__init__()
        self.executor = executor
        self._services: list[ServiceInfo] = []

    def compose(self) -> ComposeResult:
        with Container(classes="panel"):
            yield Static(
                "SERVICES — ↑/↓ select  [s]tart  [S]top  [R]estart",
                classes="panel-title",
                id="services-header",
            )
            self.status_bar = Static("loading...", id="services-status")
            yield self.status_bar
            self.table = DataTable(zebra_stripes=True, show_cursor=True, cursor_type="row")
            self.table.add_columns("SERVICE", "STATUS", "DESCRIPTION")
            yield self.table

    def update(self, services: list[ServiceInfo]) -> None:
        self._services = services
        self.table.clear()
        running = sum(1 for s in services if s.running)
        self.status_bar.update(
            f"[dim]{running}/{len(services)} running[/]"
        )
        for s in services:
            status = (
                f"[{theme.OK}]running[/]" if s.running
                else f"[{theme.STOPPED}]stopped[/]"
            )
            self.table.add_row(s.name, status, s.description)

    def action_start_service(self) -> None:
        self._run_action("start")

    def action_stop_service(self) -> None:
        self._run_action("stop")

    def action_restart_service(self) -> None:
        self._run_action("restart")

    def _run_action(self, action: str) -> None:
        info = self._selected_service()
        if info is None:
            self.app.notify("no service selected", severity="warning", timeout=3)
            return

        def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            self._execute_action(action, info)

        self.app.push_screen(ConfirmActionScreen(action, info.name), on_confirm)

    def _selected_service(self) -> ServiceInfo | None:
        coord = self.table.cursor_coordinate
        if coord.row < 0 or coord.row >= len(self._services):
            return None
        return self._services[coord.row]

    def _execute_action(self, action: str, info: ServiceInfo) -> None:
        self.app.notify(
            f"{action} {info.name}...",
            severity="information",
            timeout=3,
        )

        async def run() -> None:
            unit = info.unit if info.unit else f"{info.name}.service"
            cmd = f"systemctl {action} {unit} 2>&1"
            result = await self.executor.run(cmd, timeout=30.0)
            if result.ok:
                self.app.notify(
                    f"{action} {info.name} OK",
                    severity="information",
                    timeout=3,
                )
            else:
                self.app.notify(
                    f"{action} {info.name} failed: {result.stderr or result.stdout}",
                    severity="error",
                    timeout=6,
                )

        self.app.run_worker(run(), group="service-action", exclusive=False)
