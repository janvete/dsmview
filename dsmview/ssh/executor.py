from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import AsyncIterator, Iterable, Optional

import paramiko

from dsmview.ssh.connection import NasConnection


@dataclass(slots=True)
class CommandResult:
    cmd: str
    stdout: str
    stderr: str
    exit_status: int

    @property
    def ok(self) -> bool:
        return self.exit_status == 0


class Executor:
    """Runs read-only commands on the NAS.

    Paramiko is not thread-safe per Channel, but the underlying Transport is.
    Each `run()` opens its own exec channel so concurrent calls are fine when
    submitted through the thread pool. Use `gather()` to fan out collectors.
    """

    def __init__(self, connection: NasConnection, *, max_workers: int = 4) -> None:
        self.connection = connection
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dsmview-exec")
        self._lock = threading.Lock()

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def run_sync(self, cmd: str, *, timeout: float = 10.0) -> CommandResult:
        with self._lock:
            transport = self.connection.client.get_transport()
            if transport is None or not transport.is_active():
                self.connection.reconnect()
                transport = self.connection.client.get_transport()
            assert transport is not None
            channel = transport.open_session(timeout=timeout)
        try:
            channel.settimeout(timeout)
            channel.exec_command(cmd)
            stdout = b""
            stderr = b""
            while True:
                if channel.recv_ready():
                    stdout += channel.recv(65536)
                if channel.recv_stderr_ready():
                    stderr += channel.recv_stderr(65536)
                if channel.exit_status_ready():
                    while channel.recv_ready():
                        stdout += channel.recv(65536)
                    while channel.recv_stderr_ready():
                        stderr += channel.recv_stderr(65536)
                    break
            status = channel.recv_exit_status()
            return CommandResult(
                cmd=cmd,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_status=status,
            )
        finally:
            try:
                channel.close()
            except Exception:
                pass

    async def run(self, cmd: str, *, timeout: float = 10.0) -> CommandResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._pool, lambda: self.run_sync(cmd, timeout=timeout))

    async def gather(self, cmds: Iterable[str], *, timeout: float = 10.0) -> list[CommandResult]:
        return await asyncio.gather(*(self.run(c, timeout=timeout) for c in cmds))

    async def tail(self, path: str, *, lines: int = 200) -> AsyncIterator[str]:
        """Stream `tail -F path` line by line.

        Yields lines as they arrive. Cancelling the consumer closes the channel.
        """
        loop = asyncio.get_running_loop()
        transport = self.connection.client.get_transport()
        if transport is None or not transport.is_active():
            await loop.run_in_executor(self._pool, self.connection.reconnect)
            transport = self.connection.client.get_transport()
        assert transport is not None

        channel = transport.open_session()
        channel.exec_command(f"tail -n {lines} -F {path}")
        buffer = bytearray()
        try:
            while True:
                chunk = await loop.run_in_executor(self._pool, self._recv_chunk, channel)
                if chunk is None:
                    return
                if chunk:
                    buffer.extend(chunk)
                    while b"\n" in buffer:
                        line, _, rest = buffer.partition(b"\n")
                        buffer = bytearray(rest)
                        yield line.decode("utf-8", errors="replace")
        finally:
            try:
                channel.close()
            except Exception:
                pass

    @staticmethod
    def _recv_chunk(channel: paramiko.Channel) -> Optional[bytes]:
        if channel.exit_status_ready() and not channel.recv_ready():
            return None
        try:
            data = channel.recv(65536)
        except Exception:
            return None
        return data
