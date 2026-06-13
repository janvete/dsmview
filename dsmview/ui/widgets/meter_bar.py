from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget


class MeterBar(Widget):
    """Single-row labelled bar (e.g. CPU 47% [█████░░░░░])."""

    DEFAULT_CSS = """
    MeterBar {
        height: 1;
        width: 100%;
    }
    """

    label: reactive[str] = reactive("")
    value: reactive[float] = reactive(0.0)
    suffix: reactive[str] = reactive("")

    def __init__(self, label: str, *, color: str = "#e06c75") -> None:
        super().__init__()
        self.label = label
        self.color = color

    def update(self, value: float, suffix: str = "") -> None:
        self.value = max(0.0, min(100.0, float(value)))
        self.suffix = suffix

    def render(self) -> Text:
        width = max(10, self.size.width)
        label_part = f"{self.label:<8}"
        suffix_part = f" {self.value:5.1f}% {self.suffix}".rstrip()
        bar_space = width - len(label_part) - len(suffix_part) - 2
        bar_space = max(4, bar_space)
        filled = int(round(bar_space * self.value / 100.0))
        bar = "█" * filled + "░" * (bar_space - filled)
        text = Text()
        text.append(label_part, style="bold")
        text.append("[")
        text.append(bar, style=self.color)
        text.append("]")
        text.append(suffix_part)
        return text
