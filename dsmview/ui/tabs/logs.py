from __future__ import annotations

from collections import deque
from typing import Deque

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import RichLog, Static

from dsmview.collectors.logs import LogLine, Severity
from dsmview.ui import theme


_MAX_LINES = 2000


class LogsTab(Container):
    """Live log tail with severity filter. The filter keys (a / 1-4) are
    bound at the App level — pressing them anywhere switches to this tab
    and applies the filter."""

    def __init__(self) -> None:
        super().__init__()
        self._buffer: Deque[LogLine] = deque(maxlen=_MAX_LINES)
        self._filter: str = "ALL"

    def compose(self) -> ComposeResult:
        with Container(classes="panel"):
            yield Static(
                "LOGS — [A]LL  [1]ERROR  [2]WARN  [3]SECURITY  [4]INFO",
                classes="panel-title",
                id="logs-header",
            )
            self.status_bar = Static("filter: ALL", id="logs-status")
            yield self.status_bar
            self.log_view = RichLog(
                highlight=False, markup=True, wrap=False, max_lines=_MAX_LINES, id="logs-view"
            )
            yield self.log_view

    def set_filter(self, name: str) -> None:
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
        # Raw log lines often contain literal brackets like
        # `[/path/to/file]` which Rich's markup parser tries to interpret
        # as closing tags. Escape so they render as text.
        src = f"[dim]{line.source:<8}[/]"
        return f"{src} [{color}]{escape(line.raw)}[/]"

    def _rerender(self) -> None:
        self.log_view.clear()
        for line in self._buffer:
            if self._matches(line):
                self.log_view.write(self._format(line))
