# dsmview

TUI SSH monitor for Synology DSM 7.x — read-only dashboard inspired by `btop`.

```
brew tap janvete/tools
brew install dsmview
```

## Usage

```
dsmview ssh -p334 root@192.168.1.100
dsmview ssh root@192.168.1.100      # default port 22
dsmview ssh nas-home                # alias from ~/.ssh/config
dsmview ssh -i ~/.ssh/id_nas root@IP
```

Reads `~/.ssh/config` (HostName, Port, IdentityFile, ProxyJump). Tries
`id_ed25519`, `id_ecdsa`, `id_rsa`, then the SSH agent. Falls back to a
password prompt only when no key works.

## Read-only philosophy

The application only reads data from the NAS. No agent is installed, no
configuration is touched. The single exception is start/stop/restart of a
service — and that requires explicit confirmation in the UI.

## Tabs

- **F1 Dashboard** — CPU history graph, memory, storage pools, network
  throughput, load average, temperatures, services summary and disk health.
- **F2 Logs** — live tail of system, auth and package logs (including
  Active Backup) with severity filters and text search.
- **F3 Services** — `systemctl` service list with up/down status and
  start/stop/restart actions.

## Keys

```
F1..F3       switch tab
r            refresh now
q            quit
/            focus log search
ESC          clear log search
Logs tab:
  a / 1-4    severity filter (All / Error / Warn / Security / Info)
Services tab:
  ↑/↓        select service
  s          start
  S          stop
  R          restart
```

## Requirements

- Python 3.12+
- Synology DSM 7.x with SSH enabled and a user that can run system commands
  (typically `root` or a user in `administrators`).
