from __future__ import annotations

from collections import deque
from typing import Deque

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import RichLog, Static

from dsmview.collectors.logs import LogLine, Severity
from dsmview.ui import theme


_MAX_LINES = 2000


class LogsTab(Container):
    BINDINGS = [
        Binding("a", "filter('ALL')", "ALL", show=False),
        Binding("1", "filter('ERROR')", "ERROR", show=False),
        Binding("2", "filter('WARN')", "WARN", show=False),
        Binding("3", "filter('SECURITY')", "SECURITY", show=False),
        Binding("4", "filter('INFO')", "INFO", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._buffer: Deque[LogLine] = deque(maxlen=_MAX_LINES)
        self._filter: str = "ALL"

    def compose(self) -> ComposeResult:
        with Container(classes="panel"):
            yield Static("LOGS — [A]ll  [1]Err  [2]Warn  [3]Sec  [4]Info", classes="panel-title", id="logs-header")
            self.status_bar = Static("filter: ALL", id="logs-status")
            yield self.status_bar
            self.log_view = RichLog(highlight=False, markup=True, wrap=False, max_lines=_MAX_LINES, id="logs-view")
            yield self.log_view

    def action_filter(self, name: str) -> None:
        self._filter = name
        self.status_bar.update(f"filter: {name}")
        self._rerender()

    def push_initial(self, lines: list[LogLine]) -> None:
        self._buffer.extend(lines)
        self._rerender()

    def push(self, line: LogLine) -> None:
        self._buffer.append(line)
        if self._matches(line):
            self.log_view.write(self._format(line))

    def _matches(self, line: LogLine) -> bool:
        if self._filter == "ALL":
            return True
        return line.severity.value == self._filter

    def _format(self, line: LogLine) -> str:
        color_for = {
            Severity.ERROR: theme.LOG_ERROR,
            Severity.WARN: theme.LOG_WARN,
            Severity.INFO: theme.LOG_INFO,
            Severity.SECURITY: theme.LOG_SECURITY,
            Severity.OTHER: theme.BORDER_TITLE,
        }
        color = color_for[line.severity]
        src = f"[dim]{line.source:<8}[/]"
        return f"{src} [{color}]{line.raw}[/]"

    def _rerender(self) -> None:
        self.log_view.clear()
        for line in self._buffer:
            if self._matches(line):
                self.log_view.write(self._format(line))
