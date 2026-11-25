import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from log_analyser import __version__
from log_analyser.cli import main

LINES = [f'10.0.0.{i} - - [23/Nov/2026:09:00:00 +0000] "GET /p{i} HTTP/1.1" 200 1 "-" "x" 0.{i}\n'
         for i in range(1, 8)]
LINES += [f'10.0.0.1 - - [23/Nov/2026:10:00:00 +0000] "GET /p1 HTTP/1.1" 200 1 "-" "x" 0.1\n'] * 3   # 10.0.0.1 is busiest


@pytest.fixture
def logfile(tmp_path):
    path = tmp_path / "access.log"
    path.write_text("".join(LINES), encoding="utf-8")
    return path


def write_config(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def log_events(err):
    return [json.loads(line) for line in err.splitlines() if line.startswith("{")]


# ---------- flags ----------

def test_top_ips_flag(logfile, capsys):
    assert main([str(logfile), "--top-ips", "1"]) == 0
    out = capsys.readouterr().out
    assert "Top 1 IPs\n  10.0.0.1  4\n\n" in out


def test_config_file_is_used(logfile, tmp_path, capsys):
    config = write_config(tmp_path, "top_ips = 1\n")
    assert main([str(logfile), "--config", str(config)]) == 0
    assert "Top 1 IPs" in capsys.readouterr().out


def test_flag_overrides_config_file(logfile, tmp_path, capsys):
    config = write_config(tmp_path, "top_ips = 1\n")
    assert main([str(logfile), "--config", str(config), "--top-ips", "3"]) == 0
    assert "Top 3 IPs" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["0", "-1", "abc"])
def test_bad_flag_value_exits_2(logfile, bad, capsys):
    with pytest.raises(SystemExit) as exc:
        main([str(logfile), "--top-ips", bad])
    assert exc.value.code == 2
    assert "--top-ips" in capsys.readouterr().err


def test_log_level_is_case_insensitive(logfile, capsys):
    assert main([str(logfile), "--log-level", "info"]) == 0
    assert "start" in [e["event"] for e in log_events(capsys.readouterr().err)]


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


# ---------- config errors -> exit 1 ----------

def test_invalid_config_exits_1(logfile, tmp_path, capsys):
    config = write_config(tmp_path, "top_ips = 0\n")
    assert main([str(logfile), "--config", str(config)]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "top_ips must be at least 1" in err


def test_missing_config_exits_1(logfile, tmp_path, capsys):
    assert main([str(logfile), "--config", str(tmp_path / "nope.toml")]) == 1
    assert "cannot read config file" in capsys.readouterr().err


# ---------- logging ----------

def test_default_level_shows_no_logs_for_clean_file(logfile, capsys):
    assert main([str(logfile)]) == 0
    assert capsys.readouterr().err == ""          # WARNING level and nothing wrong: stderr stays quiet


def test_info_level_logs_all_events(logfile, capsys):
    assert main([str(logfile), "--log-level", "INFO"]) == 0
    events = log_events(capsys.readouterr().err)
    assert [e["event"] for e in events] == ["start", "config_loaded", "analysis_done"]
    done = events[-1]
    assert (done["lines"], done["valid"], done["malformed"]) == (10, 10, 0)


def test_malformed_lines_produce_warning(tmp_path, capsys):
    path = tmp_path / "mixed.log"
    path.write_text("".join(LINES) + "garbage\n\n", encoding="utf-8")
    assert main([str(path)]) == 0
    [event] = log_events(capsys.readouterr().err)
    assert event["level"] == "WARNING" and event["count"] == 2


def test_missing_logfile_logs_error_and_exits_1(tmp_path, capsys):
    assert main([str(tmp_path / "nope.log")]) == 1
    err = capsys.readouterr().err
    assert "Error: cannot read" in err
    assert log_events(err)[0]["event"] == "error"


# ---------- the installed command, end to end ----------

def test_installed_command(logfile):
    # The "log-analyser" launcher lives next to the venv's python (Scripts/ on Windows, bin/ elsewhere).
    command = shutil.which("log-analyser", path=str(Path(sys.executable).parent))
    assert command is not None, "log-analyser not installed: run  pip install -e .[dev]"
    result = subprocess.run([command, str(logfile), "--top-ips", "2"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Top 2 IPs" in result.stdout
