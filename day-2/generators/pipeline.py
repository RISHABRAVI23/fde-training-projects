import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple


def read_file_gen(path):
    with open(path, encoding="utf-8", errors="replace") as file:
        yield from file


LINE_RE = re.compile(
    r"^(?P<ip>\S+) \S+ \S+ "  # IP, then two "-" fields
    r"\[\d{2}/\w{3}/\d{4}:(?P<hour>\d{2}):\d{2}:\d{2}[^\]]*\] "  # [23/Nov/2026:09:15:00 +0000]
    r'"\S+ (?P<path>\S+)[^"]*" '  # "GET /home HTTP/1.1"
    r"(?P<status>\d{3}) "  # 200
    r".*\s(?P<time>\d+(?:\.\d+)?)\s*$"  # ... last field: 0.079
)


class Request(NamedTuple):
    """One valid log line, reduced to the fields the report needs."""

    ip: str
    hour: str  # "00".."23"
    path: str
    status: int
    time: float  # request time in seconds


def parse_line(line: str):
    """Parse one log line. Return a Request, or None if the line is malformed."""
    match = LINE_RE.match(line)
    if match is not None:
        return Request(
            ip=match["ip"],
            hour=match["hour"],
            path=match["path"],
            status=int(match["status"]),
            time=float(match["time"]),
        )
    return None


def parse(lines):
    for line in lines:
        # parsed = parse_line(line)
        # if parsed is not None:
        #     yield parsed

        # or

        if (request := parse_line(line)) is not None:
            yield request


def server_errors(requests):
    for request in requests:
        if 500 <= request.status < 600:
            yield request


if __name__ == "__main__":
    errors = server_errors(parse(read_file_gen(Path(__file__).parent / "access.log")))

    counts = Counter(request.path for request in errors)
    total = sum(counts.values())
    for path, n in counts.most_common():
        print(f"{path:<20}:    {n}")

    print(f"\nTotal = {total}")
