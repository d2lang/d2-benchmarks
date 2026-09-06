# Reference run: SVG and PNG across diagram sizes

Measured September 6, 2026 UTC (September 5 in the machine's Pacific time zone), on an Apple M4 with 16 GiB RAM. This is one desktop session with uncontrolled background activity. No other builds or tests from this task ran during measurement. The measurement phase took 21.1 minutes.

[Download the complete run](https://github.com/d2lang/d2-benchmarks/raw/refs/heads/main/examples/2026-09-06-macos-m4/reference-performance-macos-m4-2026-09-06.tar.gz) · [SHA-256 checksum](reference-performance-macos-m4-2026-09-06.tar.gz.sha256) · [Per-diagram timing CSV](summary.csv)

The archive is included in this directory when you clone the repository. Extract it and open `benchmark-run/index.html` for the performance matrix, timing distributions, 95% bootstrap intervals, and all 104 rendered outputs. It also contains raw records, source inputs and licenses, exact commands, runtime/build provenance, and an integrity manifest.

| Workload | Format | D2 / Dagre | Mermaid / Dagre | Graphviz / dot | PlantUML / Graphviz |
|---|---|---:|---:|---:|---:|
| Basic · 2 nodes | SVG | **16.9** | 357.4 | 64.2 | 854.6 |
| Basic · 2 nodes | PNG 2× | **20.6** | 400.1 | 68.1 | 886.3 |
| Basic · 10 nodes | SVG | **18.0** | 368.5 | 65.2 | 860.3 |
| Basic · 10 nodes | PNG 2× | **41.3** | 430.9 | 86.3 | 939.7 |
| Basic · 100 nodes | SVG | **26.2** | 498.6 | 68.7 | 910.7 |
| Basic · 100 nodes | PNG 2× | 459.4 | 741.7 | **315.0** | 1,314.5 |
| Real-world complex | SVG | **30.5** | 431.2 | 76.8 | 892.5 |
| Real-world complex | PNG 2× | **259.7** | 665.4 | 327.9 | 1,390.4 |
| TPMJS supplement | PNG 0.5× supplement | 360.4 | 789.4 | **184.5** | 1,363.5 |

Times are milliseconds; bold marks the lowest observed time in each row. Basic rows show the median of 20 runs. Real-world rows show the geometric mean of per-diagram medians: ten SVG diagrams and nine PNG diagrams at 2× density. TPMJS PNG uses a separate 0.5× supplement. All jobs had three excluded warm-ups. This is one Apple M4 session with uncontrolled desktop background activity; intervals and individual samples are in the reference report.

All **2,080 measured invocations and 312 excluded warm-ups succeeded**. Every one of the 104 jobs produced the same output hash across all 23 invocations. Independent checks recomputed the reported medians and aggregate latencies and verified every retained output against its recorded hash. Browser checks exercised all 104 outputs and the nine matrix rows at desktop and mobile widths.

## Reproduce this run

Measured harness commit: `d24126c6d7252c7e29bc9d3cff82527f4c8e819a`. Public D2 source: `a825194903523c4409f4df7e7f4385efacb6deeb`. Runtime versions: Mermaid CLI 11.17.0 / Mermaid 11.17.2, Node 24.19.0, Chrome Headless Shell 152.0.7977.75, Graphviz 14.1.2, PlantUML 1.2026.8, and OpenJDK 21.0.10.

```sh
git checkout d24126c6d7252c7e29bc9d3cff82527f4c8e819a
./make.sh --formats svg png --warmups 3 --repetitions 20 \
  --seed 20260905 --output results/reference-performance
```

The recorded run used the same pinned tools from an alternate local `.tools-shell/toolchain.json`; the default setup installs them into `.tools/`. Local repository path prefixes are replaced with `${REPO}` in the exported metadata, while source and rendered outputs retain their original hashes. This archive contains performance measurements and output-validation evidence; file size and compression are not benchmark metrics.

The diagrams, format, and output density define the workload. Node count alone does not express real-world complexity, and renderer defaults still produce different geometry. Read the [methodology](../../docs/METHODOLOGY.md), [corpus notes](../../corpus/README.md), and [setup details](../../docs/SETUP.md) before comparing results across machines or claiming general superiority.
