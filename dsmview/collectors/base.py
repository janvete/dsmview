from __future__ import annotations

from typing import Generic, TypeVar

from dsmview.ssh.executor import Executor

T = TypeVar("T")


class Collector(Generic[T]):
    """Base class for periodic data collectors.

    Each collector runs a small set of read-only commands and parses the
    output into a typed snapshot. A missing/failing command should yield a
    graceful partial result, not crash the UI.
    """

    name: str = "collector"

    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    async def collect(self) -> T:
        raise NotImplementedError
