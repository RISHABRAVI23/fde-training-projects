"""Command-line interface: arguments, config, logging, file handling and exit codes.

Exit codes: 0 = success, 1 = log file or config problem, 2 = bad command-line arguments.
"""
import argparse
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from . import __version__
from .config import LOG_LEVELS, ConfigError, build_config, load_config_file
from .logging_setup import configure_logging
from .report import format_report
from .stats import analyse


def positive_int(text: str) -> int:
    """argparse type: a whole number >= 1 (bad values make argparse exit with code 2)."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a whole number, got {text!r}")
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="log-analyser",
        description="Summarise a web server access log.",
        epilog="Settings precedence: built-in defaults < --config file < command-line flags.",
    )
    parser.add_argument("logfile", type=Path, help="path to the access log")
    parser.add_argument("--config", type=Path, help="TOML config file (see example-config.toml)")
    parser.add_argument("--top-ips", type=positive_int, help="how many IPs to list (default 10)")
    parser.add_argument("--top-endpoints", type=positive_int, help="how many slowest endpoints to list (default 5)")
    parser.add_argument("--log-level", type=str.upper, choices=LOG_LEVELS,
                        help="minimum level of JSON logs on stderr (default WARNING)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Optional[list] = None) -> int:
    """Command-line entry point. Returns the exit code."""
    args = build_parser().parse_args(argv)     # bad arguments: argparse prints usage and exits 2

    # 1. Settings: defaults -> config file -> flags.
    try:
        file_values = load_config_file(args.config) if args.config else {}
        config = build_config(file_values, {
            "top_ips": args.top_ips,
            "top_endpoints": args.top_endpoints,
            "log_level": args.log_level,
        })
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # 2. Logging (needs the final log level, so it comes after the config).
    log = configure_logging(config.log_level)
    log.info("start", extra={"fields": {"logfile": args.logfile, "version": __version__}})
    log.info("config_loaded", extra={"fields": {**asdict(config), "config_file": args.config}})

    # 3. Analyse, streaming the file line by line.
    try:
        with open(args.logfile, encoding="utf-8", errors="replace") as f:
            stats = analyse(f)
    except OSError as e:
        log.error("error", extra={"fields": {"logfile": args.logfile, "reason": e.strerror}})
        print(f"Error: cannot read {args.logfile}: {e.strerror}", file=sys.stderr)
        return 1

    log.info("analysis_done", extra={"fields": {
        "lines": stats.lines, "valid": stats.total, "malformed": stats.malformed,
    }})
    if stats.malformed:
        # WARNING, so it shows at the default level: skipped data is never silent.
        log.warning("malformed_lines_skipped", extra={"fields": {"count": stats.malformed}})

    # 4. Report on stdout.
    print(format_report(stats, config))
    return 0
