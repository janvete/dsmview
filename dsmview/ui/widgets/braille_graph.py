from __future__ import annotations

from collections import deque
from typing import Deque

import plotext as plt
from rich.text import Text
from textual.widget import Widget


class BrailleGraph(Widget):
    """A compact braille-dot graph rendered with plotext.

    Stores a rolling history and redraws on `push()`. Sized by Textual,
    re-rendered to fit the current widget size.
    """

    DEFAULT_CSS = """
    BrailleGraph {
        height: 100%;
        width: 100%;
    }
    """

    def __init__(self, *, max_points: int = 120, color: str = "red", y_max: float | None = None) -> None:
        super().__init__()
        self.max_points: int = max_points
        self.color: str = color
        self.y_max: float | None = y_max
        self._history: Deque[float] = deque(maxlen=max_points)

    def push(self, value: float) -> None:
        self._history.append(float(value))
        self.refresh()

    def reset(self) -> None:
        self._history.clear()
        self.refresh()

    def render(self) -> Text:
        if not self._history:
            return Text("")
        w = max(10, self.size.width - 2)
        h = max(3, self.size.height - 1)
        plt.clear_figure()
        plt.plotsize(w, h)
        plt.theme("clear")
        data = list(self._history)
        plt.plot(data, marker="braille", color=self.color)
        plt.xaxes(False, False)
        plt.yaxes(False, False)
        plt.frame(False)
        if self.y_max is not None:
            plt.ylim(0, self.y_max)
        rendered = plt.build()
        return Text.from_ansi(rendered)
