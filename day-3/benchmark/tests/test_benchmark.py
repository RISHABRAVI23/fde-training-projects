import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest
from benchmark import (
    CHUNK_SIZE,
    STRATEGIES,
    HashMismatchError,
    Result,
    Strategy,
    format_table,
    generate_files,
    hash_file,
    main,
    rotation,
    run_benchmark,
    sequential,
)

# ---------- hash_file ----------


@pytest.mark.parametrize(
    "size",
    [
        0,  # empty file: the loop never runs
        1,
        CHUNK_SIZE,  # exactly one chunk
        CHUNK_SIZE + 1,  # one full chunk + 1 byte: the chunk boundary
        3 * CHUNK_SIZE + 17,
    ],
)
def test_hash_file_matches_hashlib(tmp_path: Path, size: int) -> None:
    data = bytes(i % 251 for i in range(size))
    path = tmp_path / "f.bin"
    path.write_bytes(data)
    assert hash_file(path) == hashlib.sha256(data).hexdigest()


def test_hash_file_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        hash_file(tmp_path / "nope.bin")


# ---------- generate_files ----------


def test_generate_creates_count_and_size(tmp_path: Path) -> None:
    paths = generate_files(tmp_path / "data", count=5, size_bytes=1000)
    assert len(paths) == 5
    assert all(p.stat().st_size == 1000 for p in paths)
    assert len({hash_file(p) for p in paths}) == 5  # random content: all different


def test_generate_is_idempotent(tmp_path: Path) -> None:
    first = generate_files(tmp_path, count=3, size_bytes=100)
    before = [hash_file(p) for p in first]
    second = generate_files(tmp_path, count=3, size_bytes=100)
    assert first == second
    assert [hash_file(p) for p in second] == before  # existing files were NOT rewritten


def test_generate_rewrites_wrong_size(tmp_path: Path) -> None:
    (tmp_path / "file_00000.bin").write_bytes(b"short")
    [path] = generate_files(tmp_path, count=1, size_bytes=100)
    assert path.stat().st_size == 100


# ---------- the four strategies ----------


@pytest.fixture
def small_files(tmp_path: Path) -> list[Path]:
    return generate_files(tmp_path, count=20, size_bytes=50_000)


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_every_strategy_matches_sequential(name: str, small_files: list[Path]) -> None:
    expected = sequential(small_files, workers=1)
    assert STRATEGIES[name](small_files, 4) == expected


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_every_strategy_handles_no_files(name: str) -> None:
    assert STRATEGIES[name]([], 4) == {}


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_strategies_work_with_one_worker(name: str, small_files: list[Path]) -> None:
    assert STRATEGIES[name](small_files, 1) == sequential(small_files, 1)


def test_sequential_result_maps_each_path_to_its_hash(small_files: list[Path]) -> None:
    result = sequential(small_files, workers=1)
    assert list(result) == small_files  # keys in the same order as the input
    assert all(result[p] == hash_file(p) for p in small_files)


# ---------- the runner ----------


def test_rotation_shifts_each_round() -> None:
    names = ["a", "b", "c", "d"]
    assert rotation(names, 0) == ["a", "b", "c", "d"]
    assert rotation(names, 1) == ["b", "c", "d", "a"]
    assert rotation(names, 5) == ["b", "c", "d", "a"]  # wraps around


def test_rotation_puts_every_strategy_first_once() -> None:
    names = ["a", "b", "c", "d"]
    firsts = [rotation(names, r)[0] for r in range(len(names))]
    assert sorted(firsts) == names


def fake_clock(step: float = 1.0) -> Callable[[], float]:
    """A clock that advances by `step` every time it's read, so every run 'takes' exactly `step`."""
    now = 0.0

    def clock() -> float:
        nonlocal now
        now += step
        return now

    return clock


def fake_strategy(answer: dict[Path, str]) -> Strategy:
    def strategy(paths: list[Path], workers: int) -> dict[Path, str]:
        return answer

    return strategy


def test_run_benchmark_times_every_strategy_repeats_times() -> None:
    good = {Path("a"): "h"}
    fakes = {"sequential": fake_strategy(good), "other": fake_strategy(good)}
    results = run_benchmark(
        [], workers=2, repeats=3, strategies=fakes, clock=fake_clock(0.5)
    )
    assert {r.name: r.times for r in results} == {
        "sequential": (0.5, 0.5, 0.5),
        "other": (0.5, 0.5, 0.5),
    }


def test_run_benchmark_rejects_wrong_hashes() -> None:
    fakes = {
        "sequential": fake_strategy({Path("a"): "right"}),
        "broken": fake_strategy({Path("a"): "WRONG"}),
    }
    with pytest.raises(HashMismatchError, match="broken"):
        run_benchmark([], workers=2, repeats=1, strategies=fakes, clock=fake_clock())


def test_run_benchmark_rejects_zero_repeats() -> None:
    with pytest.raises(ValueError, match="repeats"):
        run_benchmark([], workers=1, repeats=0)


def test_run_benchmark_with_real_strategies(small_files: list[Path]) -> None:
    results = run_benchmark(small_files, workers=2, repeats=2)
    assert [r.name for r in results] == list(STRATEGIES)
    assert all(len(r.times) == 2 and r.best > 0 for r in results)


# ---------- the table ----------


def test_result_median_and_best() -> None:
    r = Result("x", (3.0, 1.0, 2.0, 10.0))
    assert r.median == 2.5  # the median ignores the one slow outlier (10.0)
    assert r.best == 1.0


def test_table_sorted_fastest_first_with_speedups() -> None:
    table = format_table(
        [Result("sequential", (4.0,)), Result("fast", (1.0,)), Result("medium", (2.0,))]
    )
    lines = table.splitlines()
    assert lines[0].split() == ["strategy", "median", "(s)", "best", "(s)", "speed-up"]
    assert [line.split()[0] for line in lines[2:]] == ["fast", "medium", "sequential"]
    assert [line.split()[-1] for line in lines[2:]] == ["4.00x", "2.00x", "1.00x"]


def test_table_requires_baseline() -> None:
    with pytest.raises(ValueError, match="sequential"):
        format_table([Result("fast", (1.0,))])


# ---------- command-line interface ----------


def test_cli_generate_then_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "data"
    assert (
        main(["generate", "--dir", str(folder), "--files", "6", "--size-kb", "20"]) == 0
    )
    assert len(list(folder.iterdir())) == 6

    assert main(["run", "--dir", str(folder), "--repeats", "1", "--workers", "2"]) == 0
    out = capsys.readouterr().out
    assert "6 files" in out
    for name in STRATEGIES:
        assert name in out
    assert "speed-up" in out


def test_cli_run_missing_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", "--dir", str(tmp_path / "nope")]) == 1
    assert "not a folder" in capsys.readouterr().err


def test_cli_run_empty_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", "--dir", str(tmp_path)]) == 1
    assert "no files" in capsys.readouterr().err


def test_cli_run_bad_repeats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generate_files(tmp_path, count=1, size_bytes=10)
    assert main(["run", "--dir", str(tmp_path), "--repeats", "0"]) == 1
    assert "repeats" in capsys.readouterr().err


def test_cli_requires_a_command() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
