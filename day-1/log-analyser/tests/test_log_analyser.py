import subprocess
import sys
import tracemalloc
from pathlib import Path

import pytest
from log_analyser import (
    Request,
    analyse,
    format_report,
    main,
    parse_line,
    top_with_ties,
)

VALID = (
    '198.51.100.5 - - [23/Nov/2026:00:01:20 +0000] "GET /products HTTP/1.1" '
    '200 31724 "-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" 0.079'
)

# The worked example from SPEC.md (5 valid lines + 1 malformed).
EXAMPLE_LINES = [
    '10.0.0.1 - - [23/Nov/2026:09:15:00 +0000] "GET /home HTTP/1.1" 200 512 "-" "curl/8.4.0" 0.100\n',
    '10.0.0.2 - - [23/Nov/2026:09:40:00 +0000] "GET /home HTTP/1.1" 404 128 "-" "curl/8.4.0" 0.300\n',
    '10.0.0.1 - - [23/Nov/2026:10:05:00 +0000] "POST /api/orders HTTP/1.1" 201 64 "-" "curl/8.4.0" 1.200\n',
    '10.0.0.3 - - [23/Nov/2026:10:30:00 +0000] "GET /reports HTTP/1.1" 500 0 "-" "curl/8.4.0" 2.000\n',
    '10.0.0.1 - - [23/Nov/2026:10:45:00 +0000] "GET /home HTTP/1.1" 200 256 "-" "curl/8.4.0" 0.200\n',
    "garbage line\n",
]


# ---------- parse_line ----------


def test_parse_valid_line():
    assert parse_line(VALID) == Request(
        ip="198.51.100.5", hour="00", path="/products", status=200, time=0.079
    )


def test_parse_ignores_trailing_newline():
    assert parse_line(VALID + "\n") == parse_line(VALID)


def test_parse_integer_time():
    line = VALID.replace(" 0.079", " 2")
    assert parse_line(line).time == 2.0


@pytest.mark.parametrize(
    "line",
    [
        "",  # empty
        "\n",  # blank
        "garbage line with no structure",  # garbage
        '203.0.113.7 - - [23/Nov/2026:15:02:11 +0000] "GET /home',  # truncated
        VALID.replace(" 0.079", " abc"),  # non-numeric time
        VALID.replace(" 0.079", ""),  # time missing
        VALID.replace('" 200 ', '" 20X '),  # bad status
        VALID.replace("00:01:20", "0:01:20"),  # bad timestamp
    ],
)
def test_parse_malformed_returns_none(line):
    assert parse_line(line) is None


# ---------- analyse ----------


def test_analyse_example_counts():
    stats = analyse(EXAMPLE_LINES)
    assert stats.total == 5  # garbage line skipped
    assert stats.status == {200: 2, 201: 1, 404: 1, 500: 1}
    assert stats.ips == {"10.0.0.1": 3, "10.0.0.2": 1, "10.0.0.3": 1}
    assert stats.hours == {"09": 2, "10": 3}


def test_analyse_average_times():
    averages = analyse(EXAMPLE_LINES).average_times()
    # pytest.approx: floats like 0.1 + 0.3 + 0.2 are not exact in binary (Day 1 fundamentals!)
    assert averages == pytest.approx(
        {"/home": 0.2, "/api/orders": 1.2, "/reports": 2.0}
    )


def test_analyse_empty_input():
    stats = analyse([])
    assert stats.total == 0
    assert stats.status == {}
    assert stats.average_times() == {}


def test_analyse_only_malformed():
    assert analyse(["", "garbage\n", "\n"]).total == 0


def test_analyse_accepts_a_generator():
    # Streaming: analyse must work on a one-pass iterator, not just a list.
    stats = analyse(line for line in EXAMPLE_LINES)
    assert stats.total == 5


# ---------- top_with_ties ----------


def test_top_simple():
    assert top_with_ties({"a": 1, "b": 3, "c": 2}, 2) == [("b", 3), ("c", 2)]


def test_top_fewer_items_than_n():
    assert top_with_ties({"a": 1}, 10) == [("a", 1)]


def test_top_ties_alphabetical():
    assert top_with_ties({"z": 5, "a": 5, "m": 5}, 3) == [("a", 5), ("m", 5), ("z", 5)]


def test_top_includes_all_tied_at_cutoff():
    # 9 IPs with distinct high counts, then 2 tied for 10th place -> 11 rows.
    counts = {f"ip{i:02d}": 100 - i for i in range(9)}
    counts.update({"tied-a": 50, "tied-b": 50, "loser": 10})
    result = top_with_ties(counts, 10)
    assert len(result) == 11
    assert result[-2:] == [("tied-a", 50), ("tied-b", 50)]
    assert ("loser", 10) not in result


def test_top_tie_above_cutoff_does_not_extend():
    # A tie at 1st place must not pull in extra rows.
    assert top_with_ties({"a": 9, "b": 9, "c": 1, "d": 0}, 3) == [
        ("a", 9),
        ("b", 9),
        ("c", 1),
    ]


def test_top_zero():
    assert top_with_ties({"a": 1}, 0) == []


# ---------- format_report ----------

# Copied exactly from the "Expected output" block in SPEC.md.
EXPECTED_EXAMPLE_REPORT = """\
Total valid requests: 5

Requests by status code
  200  2
  201  1
  404  1
  500  1

Top 10 IPs
  10.0.0.1  3
  10.0.0.2  1
  10.0.0.3  1

Slowest endpoints (average time)
  /reports     2.000s  (1 request)
  /api/orders  1.200s  (1 request)
  /home        0.200s  (3 requests)

Requests per hour
  09  2
  10  3"""


def test_report_matches_spec_example():
    assert format_report(analyse(EXAMPLE_LINES)) == EXPECTED_EXAMPLE_REPORT


def test_report_empty():
    report = format_report(analyse([]))
    assert report.startswith("Total valid requests: 0")
    for heading in [
        "Requests by status code",
        "Top 10 IPs",
        "Slowest endpoints (average time)",
        "Requests per hour",
    ]:
        assert heading in report


# ---------- main / CLI ----------


def test_main_example_file(tmp_path, capsys):
    log = tmp_path / "example.log"
    log.write_text("".join(EXAMPLE_LINES), encoding="utf-8")
    assert main([str(log)]) == 0
    out, err = capsys.readouterr()
    assert out == EXPECTED_EXAMPLE_REPORT + "\n"
    assert err == ""


def test_main_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.log")]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "Error: cannot read" in err


def test_main_directory(tmp_path, capsys):
    assert main([str(tmp_path)]) == 1
    assert "Error: cannot read" in capsys.readouterr().err


def test_main_empty_file(tmp_path, capsys):
    log = tmp_path / "empty.log"
    log.write_text("", encoding="utf-8")
    assert main([str(log)]) == 0
    assert capsys.readouterr().out.startswith("Total valid requests: 0")


def test_main_only_malformed(tmp_path, capsys):
    log = tmp_path / "bad.log"
    log.write_text("garbage\n\nmore garbage\n", encoding="utf-8")
    assert main([str(log)]) == 0
    assert capsys.readouterr().out.startswith("Total valid requests: 0")


def test_main_invalid_utf8_does_not_crash(tmp_path, capsys):
    log = tmp_path / "binary.log"
    log.write_bytes(b"\xff\xfe\x00garbage\n" + EXAMPLE_LINES[0].encode())
    assert main([str(log)]) == 0
    assert capsys.readouterr().out.startswith("Total valid requests: 1")


def test_main_no_arguments_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "usage" in capsys.readouterr().err


def test_script_runs_as_a_program(tmp_path):
    # End-to-end: run the real file with the real interpreter, check the exit code.
    script = Path(__file__).parent.parent / "log_analyser.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path / "missing.log")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Error" in result.stderr


# ---------- 500 MB log (run with: pytest --runslow) ----------


@pytest.mark.slow
def test_500mb_log_streams_with_constant_memory(tmp_path):
    # Build a ~500 MB log by repeating the example lines (5 valid + 1 malformed each block).
    block = "".join(EXAMPLE_LINES)
    target_bytes = 500 * 1024 * 1024
    repeats = target_bytes // len(block.encode()) + 1
    log = tmp_path / "big.log"
    with open(log, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(block for _ in range(repeats))
    size_mb = log.stat().st_size / (1024 * 1024)
    assert size_mb >= 500

    tracemalloc.start()
    with open(log, encoding="utf-8", errors="replace") as f:
        stats = analyse(f)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)
    print(f"\nfile: {size_mb:.0f} MB, peak memory while analysing: {peak_mb:.2f} MB")

    assert stats.total == 5 * repeats  # every block has 5 valid lines
    assert stats.ips["10.0.0.1"] == 3 * repeats
    assert peak_mb < 50  # would be ~GBs if the file were loaded whole
