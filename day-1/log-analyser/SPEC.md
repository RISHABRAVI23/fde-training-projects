# Log Analyser: Specification

A command-line tool that reads a web server access log and prints a summary report.

## Usage

```
python log_analyser.py <logfile>
```

- One required argument: the path to the log file.
- `-h` / `--help` prints usage and exits 0.

## Input format

nginx/Apache "combined" format with the request time (seconds) as the **last** field:

```
198.51.100.5 - - [23/Nov/2026:00:01:20 +0000] "GET /products HTTP/1.1" 200 31724 "-" "Mozilla/5.0 (...)" 0.079
```

| Field | Example | Used for |
|---|---|---|
| IP | `198.51.100.5` | top IPs |
| timestamp | `23/Nov/2026:00:01:20 +0000` | requests per hour |
| request | `GET /products HTTP/1.1` | endpoint (the path) |
| status | `200` | status counts |
| request time | `0.079` (last field) | slowest endpoints |

**Valid line:** has all of the fields above, a 3-digit status code and a numeric request time.
Anything else is **malformed**.

## Output

Plain-text report with four sections, printed to stdout:

1. **Requests by status code**: every status code seen, with its count, sorted by **status code ascending**.
2. **Top 10 IPs**: by request count, highest first.
3. **Slowest endpoints**: top 5 paths by **average** request time, highest first, showing the average (3 decimal places) and the number of requests.
4. **Requests per hour**: hour of day (`00`–`23`), sorted by hour. Only hours that have requests are shown. If the log spans several days, the same hour on different days is **combined**.

A header line shows the total number of valid requests.

### Ranking rules

- **Ties:** if several entries tie for the last place (10th IP, 5th endpoint), **all tied entries are included**, so the list may be longer than 10 or 5.
- Entries with equal values are listed in **alphabetical order** (IP or path), so the output is the same every run.

## Worked example

Input (`example.log`, 6 lines, the last one malformed):

```
10.0.0.1 - - [23/Nov/2026:09:15:00 +0000] "GET /home HTTP/1.1" 200 512 "-" "curl/8.4.0" 0.100
10.0.0.2 - - [23/Nov/2026:09:40:00 +0000] "GET /home HTTP/1.1" 404 128 "-" "curl/8.4.0" 0.300
10.0.0.1 - - [23/Nov/2026:10:05:00 +0000] "POST /api/orders HTTP/1.1" 201 64 "-" "curl/8.4.0" 1.200
10.0.0.3 - - [23/Nov/2026:10:30:00 +0000] "GET /reports HTTP/1.1" 500 0 "-" "curl/8.4.0" 2.000
10.0.0.1 - - [23/Nov/2026:10:45:00 +0000] "GET /home HTTP/1.1" 200 256 "-" "curl/8.4.0" 0.200
garbage line
```

Expected output:

```
Total valid requests: 5

Requests by status code
  200  3
  201  1
  404  1
  500  1

Top 10 IPs
  10.0.0.1  2
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

## Edge cases and acceptance criteria

| Situation | Behaviour | Exit code |
|---|---|---|
| Normal log | full report | 0 |
| Malformed lines | **skipped silently** (see decision note) | 0 |
| Empty file | report with `Total valid requests: 0` and empty sections | 0 |
| File with only malformed lines | same as empty file | 0 |
| File does not exist | error message on **stderr** | 1 |
| Path is a directory / not readable | error message on stderr | 1 |
| No argument / too many arguments | usage on stderr | 2 (argparse default) |
| Ties at the cut-off | all tied entries shown | 0 |
| 500 MB log | completes, memory stays roughly constant | 0 |

> **Decision note:** malformed lines are skipped *silently*. This was a deliberate choice for
> simpler output. Trade-off: a badly corrupted log would produce a misleadingly small report with no warning.

## Constraints

- Python 3, **standard library only** (`argparse`, `collections`, `re`, …).
- **Must stream the file line by line.** It must never load the whole file into memory (the 500 MB requirement).
- Read the file as UTF-8. Undecodable bytes must not crash the tool.

## Tests (pytest)

- The worked example above produces exactly the expected output.
- Empty file.
- Malformed lines (empty, garbage, truncated, non-numeric time, bad status).
- Missing file → exit 1, message on stderr.
- Ties at the 10th IP.
- A generated **500 MB** log completes, with memory measured (e.g. `tracemalloc`).
