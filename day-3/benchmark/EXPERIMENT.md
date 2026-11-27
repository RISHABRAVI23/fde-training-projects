# Concurrency benchmark: experiment design

Day 3 build: hash every file in a large folder using four strategies, and compare their speed.
This file was written **before any benchmark code existed**, so the prediction below is genuine.

## Question

Hashing a file means reading it (I/O) and computing SHA-256 over its bytes (CPU).
Which concurrency strategy hashes a folder of files fastest, and by how much?

## Prediction (made before writing any code)

| Strategy | Predicted speed-up vs sequential |
|---|---|
| sequential | 1× (the baseline) |
| threads | **faster than 1×**: hashing is done by C code that releases the GIL, so threads can hash in parallel |
| processes | **~6×**: **the winner**. Hashing is CPU-bound, and each process runs on its own core with its own GIL |
| asyncio + thread offload | **about the same as threads**: it hashes in background threads too, plus a little overhead |

**Reasoning:** hashing is CPU-bound, so the strategy that really uses several cores in parallel should win. That's processes.

## Setup

| Decision | Choice | Why |
|---|---|---|
| Machine | Windows laptop, `os.cpu_count()` = **16** | the core count caps how much parallelism is possible |
| Data | generated files of random bytes (`os.urandom`), in a Git-ignored `data/` folder | repeatable, and nothing personal is hashed |
| Dataset A ("large") | **200 files × 5 MB** = 1 GB | hashing work dominates |
| Dataset B ("small") | **2,000 files × 50 KB** ≈ 100 MB | per-file overhead (opening files, handing out tasks) matters more |
| Hash | SHA-256, reading each file in **1 MB chunks** | memory stays low however big the file is |
| Workers | the **same** for every parallel strategy: 16 by default | a fair comparison |

## The four strategies

| Strategy | Built from |
|---|---|
| sequential | a plain `for` loop |
| threads | `concurrent.futures.ThreadPoolExecutor` |
| processes | `concurrent.futures.ProcessPoolExecutor` |
| asyncio + thread offload | `asyncio.to_thread` + `asyncio.gather`, with a `Semaphore` limiting it to the worker count |

## Fairness rules

- **Warm-up pass first:** one sequential pass before timing anything. It fills the operating system's file cache, so **every** timed run reads from memory, not from disk. Otherwise, whichever strategy ran first would be unfairly slow.
- **5 runs per strategy**, reporting the **median** (one slow run, e.g. because of a background task, doesn't distort the result) and the **best**.
- **Rotating order:** within each round, the strategies run in a different order, so none of them always goes first or last.
- **Pool start-up is included** in each timing: creating a thread or process pool is part of the real cost of choosing that strategy.
- **Correctness:** every run's hashes are compared with the warm-up pass's hashes. Any mismatch stops the benchmark with an error, because a fast wrong answer is worthless.

## Results

Run on 2026-11-27 with `python benchmark.py run --dir data/<dataset> --repeats 5`.
Every run of every strategy produced hashes identical to the reference.

### Dataset A: large (200 files × 5 MB)
```
200 files, 1000.0 MB total | workers=16 | cpu_count=16 | Python 3.14.6 | GIL enabled: True
strategy         median (s)  best (s)  speed-up
-----------------------------------------------
threads               0.230     0.220     4.31x
asyncio_offload       0.266     0.255     3.74x
processes             0.815     0.758     1.22x
sequential            0.993     0.964     1.00x
```

### Dataset B: small (2,000 files × 50 KB)
```
2000 files, 97.7 MB total | workers=16 | cpu_count=16 | Python 3.14.6 | GIL enabled: True
strategy         median (s)  best (s)  speed-up
-----------------------------------------------
threads               0.704     0.644     1.92x
processes             0.904     0.864     1.49x
asyncio_offload       0.979     0.848     1.38x
sequential            1.350     1.238     1.00x
```

### Prediction vs result
| Strategy | Predicted | Dataset A | Dataset B |
|---|---|---|---|
| threads | faster than 1× | **4.31× (winner)** | **1.92× (winner)** |
| processes | ~6×, the winner | 1.22× | 1.49× |
| asyncio + offload | about the same as threads | 3.74× | 1.38× |

## Explanation

*(To be written by me after the results: what happened, and **why the results differ from my prediction, if they do**. This is the Day 3 Verify step.)*
