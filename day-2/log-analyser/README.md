# log-analyser

Summarise a web server access log: requests by status code, top IPs, slowest endpoints (average time) and requests per hour.

This is the Day 2 version of the Day 1 log analyser (`day-1/log-analyser/`), rebuilt as an installable package with a CLI, config file support and structured JSON logging. It uses only the Python standard library at runtime. The design and the reasons for it are in [`DESIGN.md`](DESIGN.md).

## Install

Requires Python 3.11+. From the repo root:

```bash
python -m venv .venv
source .venv/Scripts/activate        # Windows (Git Bash). Linux/macOS: source .venv/bin/activate
pip install -e "day-2/log-analyser[dev]"
```

`-e` installs in *editable* mode (code changes apply without reinstalling). `[dev]` adds pytest.

## Usage

```bash
log-analyser access.log
python -m log_analyser access.log                 # equivalent
log-analyser access.log --top-ips 3 --top-endpoints 2
log-analyser access.log --config example-config.toml --log-level INFO
log-analyser --help
log-analyser --version
```

The report goes to **stdout**. Logs go to **stderr**, so `log-analyser access.log > report.txt` saves just the report.

### Example output

```
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
  10  3
```

Rankings keep every entry tied at the cut-off, so "Top 10 IPs" can list more than 10 rows. Ties are ordered alphabetically.

## Configuration

Settings can come from three places. Later ones win:

**built-in defaults → `--config` file → command-line flags**

| Setting | Flag | Default | Meaning |
|---|---|---|---|
| `top_ips` | `--top-ips N` | `10` | number of IPs to list (≥ 1) |
| `top_endpoints` | `--top-endpoints N` | `5` | number of slowest endpoints to list (≥ 1) |
| `log_level` | `--log-level LEVEL` | `WARNING` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (any case) |

The config file is TOML (see [`example-config.toml`](example-config.toml)):

```toml
top_ips = 5
top_endpoints = 3
log_level = "INFO"
```

Unknown keys, wrong types and out-of-range values are rejected with an error that names the file. A bad config never silently falls back to the defaults.

## Logging

Structured logs: one JSON object per line on stderr.

```json
{"time": "2026-11-25T13:23:36+00:00", "level": "INFO", "event": "analysis_done", "lines": 3003, "valid": 3000, "malformed": 3}
```

| Event | Level | Fields |
|---|---|---|
| `start` | INFO | `logfile`, `version` |
| `config_loaded` | INFO | every setting + `config_file` |
| `analysis_done` | INFO | `lines`, `valid`, `malformed` |
| `malformed_lines_skipped` | WARNING | `count` |
| `error` | ERROR | `logfile`, `reason` |

Times are UTC. Malformed lines are skipped from the report but always counted, and reported as a WARNING.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | the log file can't be read, or the config file is missing or invalid |
| 2 | bad command-line arguments (e.g. `--top-ips 0`) |

## Tests

```bash
cd day-2/log-analyser
python -m pytest              # fast tests
python -m pytest --runslow    # also the 500 MB streaming/memory test (~45 s)
```

## Project layout

```
src/log_analyser/
├── parsing.py        Request, LINE_RE, parse_line
├── stats.py          Stats, analyse (streaming), top_with_ties
├── report.py         format_report
├── config.py         Config, ConfigError, load/validate/merge settings
├── logging_setup.py  JsonFormatter, configure_logging
├── cli.py            argparse, main(), exit codes
└── __main__.py       python -m log_analyser
tests/                pytest suite
```
