from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, List, Optional

from dsmview.collectors.base import Collector


class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"
    SECURITY = "SECURITY"
    INFO = "INFO"
    OTHER = "OTHER"


_ERROR_RE = re.compile(
    r"\b(error|fail(?:ed|ure)?|critical|EXT4-fs error|I/O error|RAID degraded|"
    r"panic|oom|crashed|corrupt|cannot|unable)\b",
    re.IGNORECASE,
)
_WARN_RE = re.compile(
    r"\b(warn(?:ing)?|temperature|fan speed|link down|throttle|offline)\b",
    re.IGNORECASE,
)
_SECURITY_RE = re.compile(
    r"\b(Failed password|Invalid user|authentication failure|sudo|"
    r"session opened|session closed)\b"
)
_INFO_RE = re.compile(
    r"\b(completed|started|stopped|success|updated|finished|backup task)\b",
    re.IGNORECASE,
)

# Try to strip leading syslog timestamp so we can show a short date prefix.
_SYSLOG_TS_RE = re.compile(
    r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}|"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[\+\-]\d{2}:\d{2}|"
    r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})"
)


@dataclass(slots=True)
class LogSource:
    path: str
    label: str


@dataclass(slots=True)
class LogLine:
    raw: str
    source: str
    severity: Severity = Severity.OTHER
    timestamp: str = ""
    message: str = ""

    @classmethod
    def classify(cls, raw: str, source: str) -> "LogLine":
        # Security patterns are more specific (e.g. "Failed password" vs bare
        # "fail") and must win over ERROR when both match.
        sev = Severity.OTHER
        if _SECURITY_RE.search(raw):
            sev = Severity.SECURITY
        elif _ERROR_RE.search(raw):
            sev = Severity.ERROR
        elif _WARN_RE.search(raw):
            sev = Severity.WARN
        elif _INFO_RE.search(raw):
            sev = Severity.INFO

        # Extract a leading timestamp, if present.
        ts_match = _SYSLOG_TS_RE.match(raw)
        timestamp = ts_match.group(1) if ts_match else ""
        message = raw[ts_match.end() :].lstrip() if ts_match else raw
        return cls(
            raw=raw,
            source=source,
            severity=sev,
            timestamp=timestamp,
            message=message,
        )


class LogCollector(Collector[List[LogLine]]):
    name = "logs"

    # (path, short_label). Paths are checked at runtime so missing files
    # simply yield no lines.
    SOURCES: tuple[LogSource, ...] = (
        LogSource("/var/log/messages", "messages"),
        LogSource("/var/log/auth.log", "auth"),
        LogSource("/var/log/packages/ActiveBackup.log", "abb-pkg"),
        # The ABB activity log is usually under /volumeX/@ActiveBackup/log.
        # The package exposes a symlink at /var/packages/ActiveBackup/target/log.
        LogSource("/var/packages/ActiveBackup/target/log/activity.log", "abb-activity"),
    )

    async def collect(self) -> List[LogLine]:
        cmds = [f"tail -n 200 {src.path} 2>/dev/null || true" for src in self.SOURCES]
        results = await self.executor.gather(cmds, timeout=10.0)
        lines: List[LogLine] = []
        for src, res in zip(self.SOURCES, results):
            for raw in res.stdout.splitlines():
                if raw.strip():
                    lines.append(LogLine.classify(raw, src.label))
        # Newest last so the RichLog scrolls to the bottom naturally.
        return lines

    async def tail(self, source_index: int = 0) -> AsyncIterator[LogLine]:
        src = self.SOURCES[source_index]
        async for raw in self.executor.tail(src.path):
            if raw.strip():
                yield LogLine.classify(raw, src.label)
