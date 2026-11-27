"""Log analyser: summarise a web server access log.

Usage: python log_analyser.py <logfile>
See SPEC.md for the full specification.
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import NamedTuple


class Request(NamedTuple):
    """One valid log line, reduced to the fields the report needs."""

    ip: str
    hour: str  # "00".."23"
    path: str
    status: int
    time: float  # request time in seconds


# One regex describing a valid line. Each (?P<name>...) is a named capture group.
LINE_RE = re.compile(
    r"^(?P<ip>\S+) \S+ \S+ "  # IP, then two "-" fields
    r"\[\d{2}/\w{3}/\d{4}:(?P<hour>\d{2}):\d{2}:\d{2}[^\]]*\] "  # [23/Nov/2026:09:15:00 +0000]
    r'"\S+ (?P<path>\S+)[^"]*" '  # "GET /home HTTP/1.1"
    r"(?P<status>\d{3}) "  # 200
    r".*\s(?P<time>\d+(?:\.\d+)?)\s*$"  # ... last field: 0.079
)


def parse_line(line: str) -> Request | None:
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


@dataclass
class Stats:
    """Running totals. Memory depends on the number of DISTINCT IPs/paths, not on file size."""

    total: int = 0
    status: Counter = field(default_factory=Counter)
    ips: Counter = field(default_factory=Counter)
    hours: Counter = field(default_factory=Counter)
    path_count: Counter = field(default_factory=Counter)
    path_time: defaultdict = field(default_factory=lambda: defaultdict(float))

    def average_times(self) -> dict:
        """Average request time per path."""
        return {
            path: self.path_time[path] / count
            for path, count in self.path_count.items()
        }


def analyse(lines: Iterable[str]) -> Stats:
    """Consume lines one at a time and build up Stats. Malformed lines are skipped silently."""
    stats = Stats()
    for line in lines:
        req = parse_line(line)
        if req is None:
            continue
        stats.total += 1
        stats.status[req.status] += 1
        stats.ips[req.ip] += 1
        stats.hours[req.hour] += 1
        stats.path_count[req.path] += 1
        stats.path_time[req.path] += req.time
    return stats


def top_with_ties(values: dict, n: int) -> list:
    """Return (key, value) pairs, highest value first, ties broken alphabetically by key.

    Keeps the first n, plus every entry tied with the nth.
    """
    if n <= 0:
        return []
    ranked = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) <= n:
        return ranked
    cutoff = ranked[n - 1][1]
    return [kv for kv in ranked if kv[1] >= cutoff]


TOP_IPS = 10
TOP_ENDPOINTS = 5


def _rows(pairs: list, fmt_value) -> list:
    """Format (name, value) pairs as indented, aligned lines."""
    if not pairs:
        return []
    width = max(len(str(name)) for name, _ in pairs)
    return [f"  {name!s:<{width}}  {fmt_value(value)}" for name, value in pairs]


def format_report(stats: Stats) -> str:
    """Build the plain-text report described in SPEC.md."""
    slowest_rows = []
    for path, avg in top_with_ties(stats.average_times(), TOP_ENDPOINTS):
        count = stats.path_count[path]
        plural = "" if count == 1 else "s"
        slowest_rows.append((path, f"{avg:.3f}s  ({count} request{plural})"))

    sections = [
        [f"Total valid requests: {stats.total}"],
        ["Requests by status code"] + _rows(sorted(stats.status.items()), str),
        [f"Top {TOP_IPS} IPs"] + _rows(top_with_ties(stats.ips, TOP_IPS), str),
        ["Slowest endpoints (average time)"] + _rows(slowest_rows, str),
        ["Requests per hour"] + _rows(sorted(stats.hours.items()), str),
    ]
    return "\n\n".join("\n".join(section) for section in sections)


def main(argv: list | None = None) -> int:
    """Command-line entry point. Returns the exit code."""
    parser = argparse.ArgumentParser(
        description="Summarise a web server access log (see SPEC.md)."
    )
    parser.add_argument("logfile", help="path to the access log")
    args = parser.parse_args(argv)  # bad arguments: argparse prints usage and exits 2

    try:
        # errors="replace": undecodable bytes become U+FFFD instead of crashing.
        # Iterating over the file object reads ONE line at a time (streaming).
        with open(args.logfile, encoding="utf-8", errors="replace") as f:
            stats = analyse(f)
    except OSError as e:
        # Covers missing file, directory, permission denied, ...
        print(f"Error: cannot read {args.logfile}: {e.strerror}", file=sys.stderr)
        return 1

    print(format_report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
