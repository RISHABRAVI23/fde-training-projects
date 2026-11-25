import pytest

from log_analyser.config import Config, ConfigError, build_config, load_config_file, validate
from log_analyser.report import format_report
from log_analyser.stats import analyse


def write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------- loading ----------

def test_load_valid_file(tmp_path):
    path = write(tmp_path, 'top_ips = 3\ntop_endpoints = 2\nlog_level = "info"\n')
    assert load_config_file(path) == {"top_ips": 3, "top_endpoints": 2, "log_level": "INFO"}


def test_load_partial_file_keeps_defaults(tmp_path):
    config = build_config(file_values=load_config_file(write(tmp_path, "top_ips = 3\n")))
    assert config == Config(top_ips=3, top_endpoints=5, log_level="WARNING")


def test_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="cannot read config file"):
        load_config_file(tmp_path / "nope.toml")


def test_invalid_toml_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config_file(write(tmp_path, "top_ips = = 3\n"))


# ---------- validation ----------

@pytest.mark.parametrize("values, message", [
    ({"colour": "red"},          "unknown setting"),
    ({"top_ips": "10"},          "whole number"),     # a string, not an int
    ({"top_ips": 2.5},           "whole number"),
    ({"top_ips": True},          "whole number"),     # bool sneaks through isinstance(x, int)!
    ({"top_ips": 0},             "at least 1"),
    ({"top_endpoints": -3},      "at least 1"),
    ({"log_level": "LOUD"},      "log_level must be one of"),
    ({"log_level": 5},           "log_level must be one of"),
])
def test_validation_errors(values, message):
    with pytest.raises(ConfigError, match=message):
        validate(values, source="test")


def test_error_message_names_the_source():
    with pytest.raises(ConfigError, match="my.toml"):
        validate({"top_ips": 0}, source="my.toml")


# ---------- precedence: defaults -> file -> CLI ----------

def test_defaults_only():
    assert build_config() == Config()


def test_file_overrides_defaults():
    assert build_config(file_values={"top_ips": 3}).top_ips == 3


def test_cli_overrides_file():
    config = build_config(file_values={"top_ips": 3}, cli_values={"top_ips": 7})
    assert config.top_ips == 7


def test_cli_none_means_not_given():
    config = build_config(file_values={"top_ips": 3}, cli_values={"top_ips": None, "log_level": None})
    assert config.top_ips == 3 and config.log_level == "WARNING"


def test_cli_values_are_validated():
    with pytest.raises(ConfigError, match="command line"):
        build_config(cli_values={"top_ips": 0})


def test_config_is_immutable():
    with pytest.raises(AttributeError):      # frozen dataclass: dataclasses.FrozenInstanceError
        Config().top_ips = 99


# ---------- report uses the config ----------

LINES = [f'10.0.0.{i} - - [23/Nov/2026:09:00:00 +0000] "GET /p{i} HTTP/1.1" 200 1 "-" "x" 0.{i}\n'
         for i in range(1, 8)]


def test_report_respects_top_ips_and_endpoints():
    report = format_report(analyse(LINES), Config(top_ips=2, top_endpoints=1))
    assert "Top 2 IPs" in report
    ip_section = report.split("Top 2 IPs\n")[1].split("\n\n")[0]
    assert len(ip_section.splitlines()) == 7    # all 7 tied at 1 request: ties at the cut-off are kept!
    endpoint_section = report.split("Slowest endpoints (average time)\n")[1].split("\n\n")[0]
    assert endpoint_section.strip().startswith("/p7")   # the slowest (0.7s)
    assert len(endpoint_section.splitlines()) == 1
