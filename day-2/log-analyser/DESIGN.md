I have picked Design A suggested by claude.
Reasons:
1. It uses packages that I already have installed and don't need to install again.
2. It uses lesser dependencies and builds on what I already know.

I am only giving up mainly on the aesthetic beauty of the UI when I choose design A.

---

## Design A: specifics (added by Claude)

### Goal
Turn the Day 1 log analyser into an installable Python package with a proper CLI, config file support and structured logging, using **only the standard library** at runtime. Day 1's code is copied, not moved, so the Day 1 deliverable stays unchanged.

### Layout (src layout)

```
day-2/log-analyser/
├── DESIGN.md
├── pyproject.toml
├── example-config.toml
├── src/log_analyser/
│   ├── __init__.py      # package version
│   ├── __main__.py      # enables: python -m log_analyser
│   ├── parsing.py       # Request, LINE_RE, parse_line
│   ├── stats.py         # Stats, analyse, top_with_ties
│   ├── report.py        # format_report
│   ├── config.py        # Config dataclass, load + validate the TOML file
│   ├── logging_setup.py # JSON log formatter + configure_logging()
│   └── cli.py           # argparse, main()
└── tests/
```

**Why a `src/` layout:** the package can only be imported once it is *installed*, so the tests check the installed package rather than accidentally importing loose files from the current folder.

**One job per module:** parsing knows nothing about reports, and the report knows nothing about the CLI. Each piece can be tested on its own.

### Command-line interface

```
log-analyser <logfile> [--config PATH] [--top-ips N] [--top-endpoints N] [--log-level LEVEL]
python -m log_analyser <logfile> ...        # same thing
```

| Exit code | Meaning |
|---|---|
| 0 | success |
| 1 | the log file can't be read, or the config file is invalid |
| 2 | bad command-line arguments (argparse default) |

### Config file (TOML, read with `tomllib`)

```toml
top_ips = 10
top_endpoints = 5
log_level = "INFO"
```

- **Precedence:** built-in defaults → config file → command-line flags (the flag wins).
- **Validation:** unknown keys, wrong types, numbers < 1 and unknown log levels → a clear error message on stderr, exit 1. A bad config never silently falls back to defaults.
- If `--config` is not given, no config file is read (no hidden "magic" file locations).

### Structured logging

- Standard `logging` module, with a custom formatter that writes **one JSON object per line** to **stderr**.
- The report stays on **stdout**, so logs never mix into the output.
- Events: `start`, `config_loaded`, `analysis_done` (with total lines, valid, malformed), `error`.
- Plus `malformed_lines_skipped` at **WARNING** level (added during the build), so skipped lines are visible even at the default level.
- Example: `{"time": "2026-11-25T18:40:00", "level": "INFO", "event": "analysis_done", "lines": 3003, "valid": 3000, "malformed": 3}`
- `--log-level` / `log_level` controls what's shown (default `WARNING`, so normal runs print only the report).
- **Change from Day 1:** malformed lines are now **counted and logged**, no longer skipped silently.

### Packaging (`pyproject.toml`)
- Build backend: `setuptools`.
- `dependencies = []`: nothing needed at runtime.
- `[project.optional-dependencies] dev = ["pytest>=8"]`.
- `[project.scripts] log-analyser = "log_analyser.cli:main"` creates the `log-analyser` command.
- Install for development: `pip install -e ".[dev]"`.

### Testing
- All Day 1 tests carried over (imports updated to the new modules).
- New tests: config loading and validation, the precedence order, the JSON log format, the malformed-line count, `python -m log_analyser`, and the installed `log-analyser` command.

