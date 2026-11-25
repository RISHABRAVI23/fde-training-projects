"""Report: turn Stats into the plain-text report."""
from .config import Config
from .stats import Stats, top_with_ties


def _rows(pairs: list, fmt_value) -> list:
    """Format (name, value) pairs as indented, aligned lines."""
    if not pairs:
        return []
    width = max(len(str(name)) for name, _ in pairs)
    return [f"  {str(name):<{width}}  {fmt_value(value)}" for name, value in pairs]


def format_report(stats: Stats, config: Config = Config()) -> str:
    """Build the plain-text report described in SPEC.md, using the limits from `config`."""
    slowest_rows = []
    for path, avg in top_with_ties(stats.average_times(), config.top_endpoints):
        count = stats.path_count[path]
        plural = "" if count == 1 else "s"
        slowest_rows.append((path, f"{avg:.3f}s  ({count} request{plural})"))

    sections = [
        [f"Total valid requests: {stats.total}"],
        ["Requests by status code"] + _rows(sorted(stats.status.items()), str),
        [f"Top {config.top_ips} IPs"] + _rows(top_with_ties(stats.ips, config.top_ips), str),
        ["Slowest endpoints (average time)"] + _rows(slowest_rows, str),
        ["Requests per hour"] + _rows(sorted(stats.hours.items()), str),
    ]
    return "\n\n".join("\n".join(section) for section in sections)
