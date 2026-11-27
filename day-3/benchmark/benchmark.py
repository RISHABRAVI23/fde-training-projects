"""Concurrency benchmark: hash every file in a folder using four strategies and compare timings.

See EXPERIMENT.md for the design and the prediction.
"""

import argparse
import asyncio
import hashlib
import os
import platform
import statistics
import sys
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

CHUNK_SIZE = 1024 * 1024  # read files 1 MB at a time

# Every strategy has the same shape: (files, number of workers) -> {file: hash}
Strategy = Callable[[list[Path], int], dict[Path, str]]


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, reading it in chunks.

    Top-level function (not nested or a lambda) so a ProcessPoolExecutor can pickle it.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(
            CHUNK_SIZE
        ):  # walrus: read, then stop when read() returns b""
            digest.update(chunk)
    return digest.hexdigest()


def generate_files(folder: Path, count: int, size_bytes: int) -> list[Path]:
    """Create `count` files of `size_bytes` random bytes in `folder`; return their paths.

    Files that already exist with the right size are kept, so re-running is fast.
    """
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(count):
        path = folder / f"file_{i:05d}.bin"
        if not (path.exists() and path.stat().st_size == size_bytes):
            path.write_bytes(os.urandom(size_bytes))
        paths.append(path)
    return paths


# ---------- the four strategies ----------


def sequential(paths: list[Path], workers: int) -> dict[Path, str]:
    """Baseline: one file after another. `workers` is ignored."""
    return {path: hash_file(path) for path in paths}


def threads(paths: list[Path], workers: int) -> dict[Path, str]:
    """A pool of threads, all in this one process (they share one GIL)."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip(paths, pool.map(hash_file, paths), strict=True))


def processes(paths: list[Path], workers: int) -> dict[Path, str]:
    """A pool of separate processes, each with its own interpreter and its own GIL."""
    # chunksize: send work to each process in batches, not one file per message.
    # Fewer messages between processes = less overhead, especially with many small files.
    chunksize = max(1, len(paths) // (workers * 4))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return dict(
            zip(paths, pool.map(hash_file, paths, chunksize=chunksize), strict=True)
        )


def asyncio_offload(paths: list[Path], workers: int) -> dict[Path, str]:
    """asyncio, with the blocking hash work pushed onto background threads."""
    return asyncio.run(_hash_all_async(paths, workers))


async def _hash_all_async(paths: list[Path], workers: int) -> dict[Path, str]:
    sem = asyncio.Semaphore(workers)  # at most `workers` files being hashed at once

    async def hash_one(path: Path) -> str:
        async with sem:
            return await asyncio.to_thread(
                hash_file, path
            )  # function and argument passed SEPARATELY

    digests = await asyncio.gather(*(hash_one(path) for path in paths))
    return dict(zip(paths, digests, strict=True))


STRATEGIES: dict[str, Strategy] = {
    "sequential": sequential,
    "threads": threads,
    "processes": processes,
    "asyncio_offload": asyncio_offload,
}


# ---------- running the benchmark ----------

BASELINE = "sequential"


class HashMismatchError(Exception):
    """A strategy produced different hashes from the reference run."""


@dataclass(frozen=True)
class Result:
    """All the timings (in seconds) for one strategy."""

    name: str
    times: tuple[float, ...]

    @property
    def median(self) -> float:
        return statistics.median(self.times)

    @property
    def best(self) -> float:
        return min(self.times)


def rotation(names: list[str], round_index: int) -> list[str]:
    """The order to run strategies in for one round: shifted by one place each round.

    Round 0: A B C D, round 1: B C D A, round 2: C D A B, ... so no strategy is always first.
    """
    shift = round_index % len(names)
    return names[shift:] + names[:shift]


def run_benchmark(
    paths: list[Path],
    workers: int,
    repeats: int,
    strategies: dict[str, Strategy] = STRATEGIES,
    clock: Callable[[], float] = time.perf_counter,
) -> list[Result]:
    """Time every strategy `repeats` times; check every run against a reference.

    `strategies` and `clock` are parameters (dependency injection) so tests can pass fakes.
    """
    if repeats < 1:
        raise ValueError(f"repeats must be at least 1, got {repeats}")

    # Warm-up: fills the OS file cache AND gives the reference hashes.
    reference = strategies[BASELINE](paths, workers)

    timings: dict[str, list[float]] = {name: [] for name in strategies}
    for round_index in range(repeats):
        for name in rotation(list(strategies), round_index):
            start = clock()
            result = strategies[name](paths, workers)
            elapsed = clock() - start
            if result != reference:
                raise HashMismatchError(
                    f"{name} produced different hashes from {BASELINE}"
                )
            timings[name].append(elapsed)

    return [Result(name, tuple(times)) for name, times in timings.items()]


def format_table(results: list[Result]) -> str:
    """A plain-text table, fastest first, with speed-up relative to the baseline's median."""
    by_name = {r.name: r for r in results}
    if BASELINE not in by_name:
        raise ValueError(f"results must include the {BASELINE!r} baseline")
    baseline = by_name[BASELINE].median

    rows = [("strategy", "median (s)", "best (s)", "speed-up")]
    for r in sorted(results, key=lambda r: r.median):
        rows.append(
            (r.name, f"{r.median:.3f}", f"{r.best:.3f}", f"{baseline / r.median:.2f}x")
        )

    widths = [max(len(row[col]) for row in rows) for col in range(4)]
    lines = [
        f"{a:<{widths[0]}}  {b:>{widths[1]}}  {c:>{widths[2]}}  {d:>{widths[3]}}"
        for a, b, c, d in rows
    ]
    lines.insert(1, "-" * len(lines[0]))
    return "\n".join(lines)


# ---------- command-line interface ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="Hash a folder of files with four strategies and compare.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="create a folder of random test files")
    gen.add_argument(
        "--dir", type=Path, required=True, help="folder to create the files in"
    )
    gen.add_argument("--files", type=int, required=True, help="number of files")
    gen.add_argument(
        "--size-kb", type=int, required=True, help="size of each file, in KB"
    )

    run = sub.add_parser("run", help="run the benchmark on a folder")
    run.add_argument("--dir", type=Path, required=True, help="folder of files to hash")
    run.add_argument(
        "--repeats", type=int, default=5, help="timed runs per strategy (default 5)"
    )
    run.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 4,
        help="workers (default: CPU count)",
    )
    return parser


def describe_environment(paths: list[Path], workers: int) -> str:
    """One line of context, so a results table can be interpreted later."""
    total_mb = sum(p.stat().st_size for p in paths) / (1024 * 1024)
    # sys._is_gil_enabled() exists on Python 3.13+; older versions always have the GIL.
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    return (
        f"{len(paths)} files, {total_mb:.1f} MB total | workers={workers} | "
        f"cpu_count={os.cpu_count()} | Python {platform.python_version()} | GIL enabled: {gil}"
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "generate":
        paths = generate_files(args.dir, args.files, args.size_kb * 1024)
        print(f"{len(paths)} files of {args.size_kb} KB in {args.dir}")
        return 0

    # command == "run"
    if not args.dir.is_dir():
        print(f"Error: not a folder: {args.dir}", file=sys.stderr)
        return 1
    paths = sorted(p for p in args.dir.iterdir() if p.is_file())
    if not paths:
        print(f"Error: no files in {args.dir}", file=sys.stderr)
        return 1

    print(describe_environment(paths, args.workers))
    try:
        results = run_benchmark(paths, args.workers, args.repeats)
    except (HashMismatchError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(format_table(results))
    return 0


if __name__ == "__main__":  # REQUIRED: worker processes re-import this file on Windows
    sys.exit(main())
