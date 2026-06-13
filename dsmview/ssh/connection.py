from __future__ import annotations

import getpass
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import paramiko
from paramiko.config import SSHConfig

DEFAULT_KEY_NAMES = ("id_ed25519", "id_ecdsa", "id_rsa")


@dataclass
class SshTarget:
    """Resolved SSH connection parameters after merging CLI args and ssh_config."""

    host: str
    port: int = 22
    user: str = "root"
    identity_file: Optional[str] = None
    proxy_jump: Optional[str] = None
    original: str = ""

    @property
    def label(self) -> str:
        return f"{self.user}@{self.host}:{self.port}"


def parse_target(
    spec: str,
    explicit_port: Optional[int] = None,
    explicit_identity: Optional[str] = None,
    ssh_config_path: Optional[Path] = None,
) -> SshTarget:
    """Parse user@host[:port] or an ssh_config alias into an SshTarget.

    Explicit CLI flags (-p, -i) override values from ssh_config.
    """
    original = spec
    user: Optional[str] = None
    host = spec
    port: Optional[int] = None

    if "@" in host:
        user, host = host.split("@", 1)
    if ":" in host:
        host, port_s = host.rsplit(":", 1)
        port = int(port_s)

    if ssh_config_path is None:
        ssh_config_path = Path.home() / ".ssh" / "config"

    cfg_user: Optional[str] = None
    cfg_port: Optional[int] = None
    cfg_host: Optional[str] = None
    cfg_identity: Optional[str] = None
    cfg_proxy: Optional[str] = None

    if ssh_config_path.exists():
        cfg = SSHConfig()
        with open(ssh_config_path) as fh:
            cfg.parse(fh)
        lookup = cfg.lookup(host)
        cfg_host = lookup.get("hostname")
        cfg_user = lookup.get("user")
        if lookup.get("port"):
            cfg_port = int(lookup["port"])
        identities = lookup.get("identityfile")
        if identities:
            cfg_identity = identities[0] if isinstance(identities, list) else identities
        cfg_proxy = lookup.get("proxyjump")

    resolved_host = cfg_host or host
    resolved_user = user or cfg_user or os.environ.get("USER") or "root"
    resolved_port = explicit_port or port or cfg_port or 22
    resolved_identity = explicit_identity or cfg_identity

    return SshTarget(
        host=resolved_host,
        port=resolved_port,
        user=resolved_user,
        identity_file=resolved_identity,
        proxy_jump=cfg_proxy,
        original=original,
    )


@dataclass
class NasConnection:
    """Live SSH connection to a Synology NAS.

    Tries identity files in the canonical order, falls back to agent, then
    prompts for a password. Keepalive is enabled so long-running tails do
    not get killed by upstream firewalls.
    """

    target: SshTarget
    client: paramiko.SSHClient = field(init=False)
    _proxy_sock: Optional[paramiko.Channel] = field(init=False, default=None)
    _password: Optional[str] = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self, *, password: Optional[str] = None, timeout: float = 10.0) -> None:
        sock = self._build_proxy_sock() if self.target.proxy_jump else None
        identities = self._candidate_identities()

        last_exc: Optional[Exception] = None
        for identity in identities:
            try:
                self.client.connect(
                    hostname=self.target.host,
                    port=self.target.port,
                    username=self.target.user,
                    key_filename=str(identity) if identity else None,
                    allow_agent=True,
                    look_for_keys=identity is None,
                    timeout=timeout,
                    banner_timeout=timeout,
                    auth_timeout=timeout,
                    sock=sock,
                )
                self._enable_keepalive()
                return
            except paramiko.AuthenticationException as e:
                last_exc = e
                continue
            except (paramiko.SSHException, socket.error) as e:
                raise ConnectionError(f"SSH connection failed: {e}") from e

        pw = password if password is not None else getpass.getpass(
            f"Password for {self.target.label}: "
        )
        self._password = pw
        try:
            self.client.connect(
                hostname=self.target.host,
                port=self.target.port,
                username=self.target.user,
                password=pw,
                allow_agent=False,
                look_for_keys=False,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                sock=sock,
            )
            self._enable_keepalive()
        except paramiko.AuthenticationException as e:
            raise PermissionError(
                f"Authentication failed for {self.target.label}"
            ) from e

    def reconnect(self) -> None:
        self.close()
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connect(password=self._password)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass
        if self._proxy_sock is not None:
            try:
                self._proxy_sock.close()
            except Exception:
                pass
            self._proxy_sock = None

    def _candidate_identities(self) -> list[Optional[Path]]:
        identities: list[Optional[Path]] = []
        if self.target.identity_file:
            identities.append(Path(os.path.expanduser(self.target.identity_file)))
            return identities
        ssh_dir = Path.home() / ".ssh"
        for name in DEFAULT_KEY_NAMES:
            p = ssh_dir / name
            if p.exists():
                identities.append(p)
        identities.append(None)
        return identities

    def _enable_keepalive(self) -> None:
        transport = self.client.get_transport()
        if transport is not None:
            transport.set_keepalive(15)

    def _build_proxy_sock(self) -> Optional[paramiko.Channel]:
        jump = self.target.proxy_jump
        if jump is None:
            return None

        jump_user: Optional[str] = None
        jump_host = jump
        jump_port = 22
        if "@" in jump_host:
            jump_user, jump_host = jump_host.split("@", 1)
        if ":" in jump_host:
            jump_host, port_s = jump_host.rsplit(":", 1)
            jump_port = int(port_s)

        jump_client = paramiko.SSHClient()
        jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        jump_client.connect(
            hostname=jump_host,
            port=jump_port,
            username=jump_user or self.target.user,
            allow_agent=True,
            look_for_keys=True,
            timeout=10,
        )
        transport = jump_client.get_transport()
        assert transport is not None
        channel = transport.open_channel(
            "direct-tcpip",
            (self.target.host, self.target.port),
            ("127.0.0.1", 0),
        )
        self._proxy_sock = channel
        return channel

    def __enter__(self) -> "NasConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
