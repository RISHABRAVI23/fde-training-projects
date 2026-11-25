"""Parsing: turn one raw log line into a Request (or None if malformed)."""
import re
from typing import NamedTuple, Optional


class Request(NamedTuple):
    """One valid log line, reduced to the fields the report needs."""
    ip: str
    hour: str      # "00".."23"
    path: str
    status: int
    time: float    # request time in seconds


# One regex describing a valid line. Each (?P<name>...) is a named capture group.
LINE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ '                                    # IP, then two "-" fields
    r'\[\d{2}/\w{3}/\d{4}:(?P<hour>\d{2}):\d{2}:\d{2}[^\]]*\] '  # [23/Nov/2026:09:15:00 +0000]
    r'"\S+ (?P<path>\S+)[^"]*" '                                # "GET /home HTTP/1.1"
    r'(?P<status>\d{3}) '                                       # 200
    r'.*\s(?P<time>\d+(?:\.\d+)?)\s*$'                          # ... last field: 0.079
)


def parse_line(line: str) -> Optional[Request]:
    """Parse one log line. Return a Request, or None if the line is malformed."""
    match = LINE_RE.match(line)
    if match is None:
        return None
    return Request(
        ip=match["ip"],
        hour=match["hour"],
        path=match["path"],
        status=int(match["status"]),
        time=float(match["time"]),
    )
