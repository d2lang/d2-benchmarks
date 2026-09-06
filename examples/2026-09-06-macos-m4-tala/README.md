# Reference run: SVG and PNG including D2 / TALA

**Results — September 6, 2026 (UTC) · Apple M4 · milliseconds**

| Workload | Format | D2 / Dagre | D2 / TALA | Mermaid / Dagre | Graphviz / dot | PlantUML / Graphviz |
|---|---|---:|---:|---:|---:|---:|
| Basic · 2 nodes | SVG | **17.6** | 20.9 | 368.8 | 66.6 | 856.8 |
| Basic · 2 nodes | PNG 2× | **21.2** | 26.8 | 404.0 | 68.6 | 905.7 |
| Basic · 10 nodes | SVG | **18.4** | 22.4 | 369.4 | 65.7 | 854.9 |
| Basic · 10 nodes | PNG 2× | 41.3 | **38.1** | 415.9 | 87.6 | 951.5 |
| Basic · 100 nodes | SVG | **27.7** | 127.4 | 506.8 | 68.7 | 929.6 |
| Basic · 100 nodes | PNG 2× | 468.1 | 392.3 | 748.1 | **317.9** | 1,339.2 |
| Real-world complex | SVG | **31.1** | 126.7 | 433.0 | 79.2 | 903.2 |
| Real-world complex | PNG 2× | **264.5** | 302.2 | 684.6 | 331.6 | 1,420.1 |
| TPMJS supplement | PNG 0.5× supplement | 367.1 | 3,634.2 | 802.6 | **187.3** | 1,387.0 |

Times are milliseconds; bold marks the lowest observed time in each row. Basic rows show the median of 20 runs. Real-world rows show the geometric mean of per-diagram medians: ten SVG diagrams and nine PNG diagrams at 2× density. TPMJS PNG uses a separate 0.5× supplement. All jobs had three excluded warm-ups. This is one Apple M4 session with uncontrolled desktop background activity; intervals and individual samples are in the reference report.

D2 / TALA uses private staging commit `3b6ba0e25fd36522021fa3b84cb4a8a08a651799` with `--tala-seeds 1,2,3`. D2 / Dagre uses public commit `a825194903523c4409f4df7e7f4385efacb6deeb`. These are separate CLI builds, so the results include build differences as well as layout choice.

Measured from **04:42:45 to 05:09:09 UTC** on September 6, 2026 (September 5 in the machine's Pacific time zone), on an Apple M4 with 16 GiB RAM. The measurement phase took **26.4 minutes**. Builds and tool setup were completed before timing.

[Download the complete run](https://github.com/d2lang/d2-benchmarks/raw/refs/heads/main/examples/2026-09-06-macos-m4-tala/reference-performance-tala-macos-m4-2026-09-06.tar.gz) · [SHA-256 checksum](reference-performance-tala-macos-m4-2026-09-06.tar.gz.sha256) · [Per-diagram timing CSV](summary.csv)

The archive is included in this directory when you clone the repository. Extract it and open `benchmark-run/index.html` for the performance matrix, timing distributions, 95% bootstrap intervals, and all **130 rendered outputs**. It also contains raw records, source inputs and licenses, exact commands, runtime/build provenance, and an integrity manifest. It contains no private TALA source or executable.

All **2,600 measured invocations and 390 excluded warm-ups succeeded**. Every one of the 130 jobs produced the same output hash across all 23 invocations. Independent checks recomputed the reported medians and aggregate latencies and verified every retained output against its recorded hash.

## Reproduce this run

Measured harness commit: `0820bc45b30daf9b40ac70cbc663ef358f234599`, with a clean working tree. Runtime versions: Go 1.27.0, Mermaid CLI 11.17.0 / Mermaid 11.17.2, Node 24.19.0, Chrome Headless Shell 152.0.7977.75, Graphviz 14.1.2, PlantUML 1.2026.8, and OpenJDK 21.0.10.

TALA is optional and requires your own authorized access to the private staging source or executable. After checking out the measured harness, follow the [optional TALA recipe](../../docs/CUSTOM-TOOLS.md#optional-d2--tala) to build the pinned staging revision and create `.tools-tala/toolchain.json`, then run the command below. The fixed TALA seeds are `1,2,3`; the runner's `--seed` separately controls the randomized sampling order.

```sh
git checkout 0820bc45b30daf9b40ac70cbc663ef358f234599
# Build and configure TALA using docs/CUSTOM-TOOLS.md, then:
./make.sh --toolchain .tools-tala/toolchain.json \
  --tools d2-dagre d2-tala mermaid-dagre graphviz-dot plantuml-dot \
  --formats svg png --warmups 3 --repetitions 20 \
  --seed 20260905 --output results/reference-performance-tala
```

Plain `./make.sh` continues to install and measure the four public tools without private access. The earlier [four-tool public reference](../2026-09-06-macos-m4/README.md) is retained as a separate session; the five-tool table above uses only this run's measurements.

The recorded run reused the pinned public tools from an alternate local `.tools-shell/` installation; the standard recipe installs them into `.tools/`. Local repository path prefixes are replaced with `${REPO}` in the exported metadata, while source inputs and rendered outputs retain their original hashes. This archive contains performance measurements and output-validation evidence; file size and compression are not benchmark metrics.

The diagrams, format, and output density define the workload. Node count alone does not express real-world complexity, and renderer defaults still produce different geometry. Read the [methodology](../../docs/METHODOLOGY.md), [corpus notes](../../corpus/README.md), and [setup details](../../docs/SETUP.md) before comparing results across machines or claiming general superiority.
