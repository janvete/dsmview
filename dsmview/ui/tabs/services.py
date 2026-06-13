from __future__ import annotations

from typing import Callable, Iterable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Static

from dsmview.collectors.services import ServiceInfo
from dsmview.ui.widgets import ServiceList


class ServicesTab(Container):
    BINDINGS = [
        Binding("r", "service_action('restart')", "Restart", show=False),
        Binding("s", "service_action('stop')", "Stop", show=False),
        Binding("S", "service_action('start')", "Start", show=False),
    ]

    def __init__(self, on_action: Callable[[str, str], None]) -> None:
        super().__init__()
        self._on_action = on_action

    def compose(self) -> ComposeResult:
        with Container(classes="panel"):
            yield Static(
                "SERVICES — [enter] detail  [r] restart  [s] stop  [S] start",
                classes="panel-title",
            )
            self.table = ServiceList()
            yield self.table

    def update_services(self, services: Iterable[ServiceInfo]) -> None:
        self.table.update_services(services)

    def action_service_action(self, action: str) -> None:
        row = self.table.cursor_row
        if row is None or row < 0 or row >= self.table.row_count:
            return
        row_key = self.table.coordinate_to_cell_key((row, 0)).row_key
        name = row_key.value if row_key else None
        if not name:
            return
        self._on_action(action, name)
