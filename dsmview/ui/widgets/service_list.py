from __future__ import annotations

from typing import Iterable

from textual.widgets import DataTable

from dsmview.collectors.services import ServiceInfo
from dsmview.ui import theme


class ServiceList(DataTable):
    """Tabular service overview backed by Textual's DataTable."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = False
        self.add_columns("SERVICE", "STATUS", "INFO")

    def update_services(self, services: Iterable[ServiceInfo]) -> None:
        self.clear()
        for svc in services:
            status_text = "[green]✅ running[/]" if svc.running else "[grey50]⛔ stopped[/]"
            info = svc.status_text.splitlines()[0] if svc.status_text else ""
            self.add_row(svc.name, status_text, info, key=svc.name)
