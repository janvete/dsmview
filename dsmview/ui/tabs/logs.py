from __future__ import annotations

from collections import deque
from typing import Deque

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Input, RichLog, Static

from dsmview.collectors.logs import LogLine, Severity
from dsmview.ui import theme


_MAX_LINES = 2000


class LogsTab(Container):
    """Live log tail with severity and text filters.

    Severity filters (a / 1-4) are bound at the App level. Press ``/`` to
    start a text search and ``escape`` to clear it.
    """

    def __init__(self) -> None:
        super().__init__()
        self._buffer: Deque[LogLine] = deque(maxlen=_MAX_LINES)
        self._severity: str = "ALL"
        self._search: str = ""

    def compose(self) -> ComposeResult:
        with Container(classes="panel"):
            yield Static(
                "LOGS — [A]LL  [1]ERROR  [2]WARN  [3]SECURITY  [4]INFO  [/]/ search  ESC clear",
                classes="panel-title",
                id="logs-header",
            )
            self.status_bar = Static("filter: ALL", id="logs-status")
            yield self.status_bar
            self.search_input = Input(
                placeholder="search logs...",
                id="logs-search",
            )
            self.search_input.display = False
            yield self.search_input
            self.log_view = RichLog(
                highlight=False,
                markup=True,
                wrap=False,
                max_lines=_MAX_LINES,
                id="logs-view",
            )
            yield self.log_view

    def set_filter(self, name: str) -> None:
        self._severity = name
        self._update_status()
        self._rerender()

    def set_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self._update_status()
        self._rerender()

    def show_search(self) -> None:
        self.search_input.display = True
        self.search_input.focus()

    def hide_search(self) -> None:
        self.search_input.display = False
        self.search_input.value = ""
        self.set_search("")
        self.log_view.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "logs-search":
            self.set_search(event.value)

    def push_initial(self, lines: list[LogLine]) -> None:
        self._buffer.extend(lines)
        self._rerender()

    def push(self, line: LogLine) -> None:
        self._buffer.append(line)
        if self._matches(line):
            self.log_view.write(self._format(line))

    def _matches(self, line: LogLine) -> bool:
        if self._severity != "ALL" and line.severity.value != self._severity:
            return False
        if self._search:
            haystack = (line.raw + " " + line.source).lower()
            return self._search in haystack
        return True

    def _format(self, line: LogLine) -> str:
        color_for = {
            Severity.ERROR: theme.LOG_ERROR,
            Severity.WARN: theme.LOG_WARN,
            Severity.INFO: theme.LOG_INFO,
            Severity.SECURITY: theme.LOG_SECURITY,
            Severity.OTHER: theme.BORDER_TITLE,
        }
        color = color_for[line.severity]
        ts = escape(line.timestamp) if line.timestamp else ""
        ts_part = f"[dim]{ts:<28}[/] " if ts else ""
        src = f"[dim]{line.source:<12}[/]"
        body = escape(line.message or line.raw)
        return f"{ts_part}{src} [{color}]{body}[/]"

    def _update_status(self) -> None:
        parts = [f"severity: {self._severity}"]
        if self._search:
            parts.append(f"search: \"{self._search}\"")
        self.status_bar.update("  ".join(parts))

    def _rerender(self) -> None:
        self.log_view.clear()
        for line in self._buffer:
            if self._matches(line):
                self.log_view.write(self._format(line))
