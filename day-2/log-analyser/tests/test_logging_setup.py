import json
import logging
import sys
from pathlib import Path

from log_analyser.logging_setup import JsonFormatter, configure_logging


def make_record(msg, level=logging.INFO, fields=None, exc_info=None):
    record = logging.LogRecord("log_analyser", level, __file__, 1, msg, None, exc_info)
    if fields is not None:
        record.fields = fields
    return record


def test_formatter_outputs_one_line_of_valid_json():
    line = JsonFormatter().format(make_record("start"))
    assert "\n" not in line
    entry = json.loads(line)  # raises if not valid JSON
    assert entry["event"] == "start"
    assert entry["level"] == "INFO"
    assert entry["time"].endswith("+00:00")  # ISO 8601, UTC


def test_formatter_includes_extra_fields():
    line = JsonFormatter().format(
        make_record("analysis_done", fields={"lines": 3003, "malformed": 3})
    )
    entry = json.loads(line)
    assert entry["lines"] == 3003 and entry["malformed"] == 3


def test_formatter_handles_non_json_values():
    entry = json.loads(
        JsonFormatter().format(make_record("x", fields={"path": Path("a/b.log")}))
    )
    assert entry["path"] in (
        "a/b.log",
        "a\\b.log",
    )  # Path turned into text (separator depends on OS)


def test_formatter_includes_exception_traceback():
    try:
        raise ZeroDivisionError("deliberate error for the test")
    except ZeroDivisionError:
        record = make_record("error", level=logging.ERROR, exc_info=sys.exc_info())
    entry = json.loads(JsonFormatter().format(record))
    assert "ZeroDivisionError" in entry["exception"]


def test_logs_go_to_stderr_not_stdout(capsys):
    log = configure_logging("INFO")
    log.info("start")
    out, err = capsys.readouterr()
    assert out == ""
    assert json.loads(err)["event"] == "start"


def test_level_filters_messages(capsys):
    log = configure_logging("WARNING")
    log.info("hidden")
    log.warning("shown")
    lines = capsys.readouterr().err.splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["shown"]


def test_configuring_twice_does_not_duplicate_output(capsys):
    configure_logging("INFO")
    log = configure_logging("INFO")
    log.info("once")
    assert len(capsys.readouterr().err.splitlines()) == 1
