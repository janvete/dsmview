from __future__ import annotations

import sys
from typing import Optional

import click

from dsmview import __version__
from dsmview.ssh.connection import NasConnection, parse_target


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="dsmview")
def main() -> None:
    """TUI monitor for Synology DSM 7.x over SSH (read-only)."""


@main.command()
@click.argument("target", required=True)
@click.option("-p", "--port", type=int, default=None, help="SSH port (default 22 or from ssh_config)")
@click.option("-i", "--identity", "identity_file", type=str, default=None, help="Explicit SSH private key file")
def ssh(target: str, port: Optional[int], identity_file: Optional[str]) -> None:
    """Connect to a NAS and launch the TUI.

    Examples:

        dsmview ssh -p334 root@192.168.1.100
        dsmview ssh root@192.168.1.100
        dsmview ssh nas-home                 # alias from ~/.ssh/config
        dsmview ssh -i ~/.ssh/id_nas root@IP
    """
    resolved = parse_target(target, explicit_port=port, explicit_identity=identity_file)
    conn = NasConnection(target=resolved)
    try:
        click.echo(f"Connecting to {resolved.label}...", err=True)
        conn.connect()
    except PermissionError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(2)
    except ConnectionError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(2)
    except KeyboardInterrupt:
        click.echo("aborted", err=True)
        sys.exit(130)

    from dsmview.ui import DsmviewApp

    app = DsmviewApp(connection=conn)
    try:
        app.run()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
