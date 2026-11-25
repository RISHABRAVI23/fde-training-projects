"""Stats: stream lines through the parser and accumulate running totals."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from .parsing import parse_line


@dataclass
class Stats:
    """Running totals. Memory depends on the number of DISTINCT IPs/paths, not on file size."""
    lines: int = 0       # every line read, valid or not
    malformed: int = 0   # lines that could not be parsed
    total: int = 0       # valid requests (lines - malformed)
    status: Counter = field(default_factory=Counter)
    ips: Counter = field(default_factory=Counter)
    hours: Counter = field(default_factory=Counter)
    path_count: Counter = field(default_factory=Counter)
    path_time: defaultdict = field(default_factory=lambda: defaultdict(float))

    def average_times(self) -> dict:
        """Average request time per path."""
        return {path: self.path_time[path] / count for path, count in self.path_count.items()}


def analyse(lines: Iterable[str]) -> Stats:
    """Consume lines one at a time and build up Stats. Malformed lines are skipped but COUNTED."""
    stats = Stats()
    for line in lines:
        stats.lines += 1
        req = parse_line(line)
        if req is None:
            stats.malformed += 1
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
