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


_ERROR_RE = re.compile(r"\b(error|fail(?:ed|ure)?|critical|EXT4-fs error|I/O error|RAID degraded|panic|oom)\b", re.IGNORECASE)
_WARN_RE = re.compile(r"\b(warn(?:ing)?|temperature|fan speed|link down|throttle)\b", re.IGNORECASE)
_SECURITY_RE = re.compile(r"\b(Failed password|Invalid user|authentication failure|sudo|session opened|session closed)\b")
_INFO_RE = re.compile(r"\b(completed|started|stopped|success|updated|finished)\b", re.IGNORECASE)


@dataclass(slots=True)
class LogLine:
    raw: str
    source: str
    severity: Severity = Severity.OTHER

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
        return cls(raw=raw, source=source, severity=sev)


class LogCollector(Collector[List[LogLine]]):
    name = "logs"

    SOURCES = (
        ("/var/log/messages", "messages"),
        ("/var/log/auth.log", "auth"),
    )

    async def collect(self) -> List[LogLine]:
        cmds = [f"tail -n 200 {path} 2>/dev/null || true" for path, _ in self.SOURCES]
        results = await self.executor.gather(cmds, timeout=10.0)
        lines: List[LogLine] = []
        for (_, source), res in zip(self.SOURCES, results):
            for raw in res.stdout.splitlines():
                if raw.strip():
                    lines.append(LogLine.classify(raw, source))
        return lines

    async def tail(self, source_index: int = 0) -> AsyncIterator[LogLine]:
        path, source = self.SOURCES[source_index]
        async for raw in self.executor.tail(path):
            if raw.strip():
                yield LogLine.classify(raw, source)
