# Reference run: current D2 and TALA staging

**Results — September 7, 2026 (UTC) · Apple M4 · milliseconds**

| Workload | Format | D2 / Dagre | D2 / TALA | Mermaid / Dagre | Graphviz / dot | PlantUML / Graphviz |
|---|---|---:|---:|---:|---:|---:|
| Basic · 2 nodes | SVG | **18.9** | 22.1 | 394.9 | 69.2 | 865.8 |
| Basic · 2 nodes | PNG 2× | **22.0** | 28.2 | 411.1 | 68.4 | 904.4 |
| Basic · 10 nodes | SVG | **19.8** | 22.6 | 388.5 | 71.7 | 877.3 |
| Basic · 10 nodes | PNG 2× | 42.8 | **39.9** | 469.3 | 91.8 | 981.7 |
| Basic · 100 nodes | SVG | **32.4** | 105.0 | 523.7 | 72.0 | 946.4 |
| Basic · 100 nodes | PNG 2× | 540.8 | 380.3 | 805.5 | **323.2** | 1,361.9 |
| Real-world complex | SVG | **30.8** | 125.6 | 461.1 | 80.4 | 928.7 |
| Real-world complex | PNG 2× | **269.5** | 310.3 | 723.5 | 340.1 | 1,480.2 |
| TPMJS supplement | PNG 0.5× supplement | 305.8 | 2,894.4 | 854.8 | **197.8** | 1,405.6 |

Basic rows are medians of 20 runs after three excluded warm-ups. Real-world rows are geometric means of per-diagram medians: ten SVG diagrams and nine PNG diagrams at 2× density. TPMJS PNG is a separate 0.5× supplement. Bold marks the lowest observed time. Timings include CLI startup, layout, rendering, output writing, and process exit.

The five-tool run took **28.2 minutes**, from **20:33:23 to 21:01:35 UTC**, on an Apple M4 with 16 GiB RAM. All **2,600 measured invocations and 390 warm-ups succeeded**; all 130 jobs produced stable output hashes. Background activity was uncontrolled, including CPU-load spikes. Every sample is retained.

## Changes since September 6

The corpus, image densities, Go version, build flags, seeds, and non-D2 executables are unchanged from the [previous five-tool reference](../2026-09-06-macos-m4-tala/README.md). Only the public D2 and private TALA builds changed. Negative percentages mean lower latency. These are comparisons between desktop sessions, not isolated code effects.

| Workload | Format | D2 / Dagre: previous → current (ms) | Change | D2 / TALA: previous → current (ms) | Change |
|---|---|---:|---:|---:|---:|
| Basic · 2 nodes | SVG | 17.6 → 18.9 | +7.1% | 20.9 → 22.1 | +5.6% |
| Basic · 2 nodes | PNG 2× | 21.2 → 22.0 | +3.9% | 26.8 → 28.2 | +5.3% |
| Basic · 10 nodes | SVG | 18.4 → 19.8 | +7.4% | 22.4 → 22.6 | +0.9% |
| Basic · 10 nodes | PNG 2× | 41.3 → 42.8 | +3.8% | 38.1 → 39.9 | +4.7% |
| Basic · 100 nodes | SVG | 27.7 → 32.4 | +17.0% | 127.4 → 105.0 | -17.6% |
| Basic · 100 nodes | PNG 2× | 468.1 → 540.8 | +15.5% | 392.3 → 380.3 | -3.1% |
| Real-world complex | SVG | 31.1 → 30.8 | -0.8% | 126.7 → 125.6 | -0.9% |
| Real-world complex | PNG 2× | 264.5 → 269.5 | +1.9% | 302.2 → 310.3 | +2.7% |
| TPMJS supplement | PNG 0.5× supplement | 367.1 → 305.8 | -16.7% | 3,634.2 → 2,894.4 | -20.4% |

The unchanged Mermaid, Graphviz, and PlantUML real-world SVG averages rose by 6.5%, 1.5%, and 2.8%; their PNG averages rose by 5.7%, 2.6%, and 4.2%. That session drift makes small historical differences inconclusive. The interleaved build comparison below measures old and new binaries in the same session.

All 26 D2 / Dagre outputs are byte-identical to the previous reference. TALA changed the SVG and PNG outputs for Mocha SoC, Queue Workers, ROSS Overview, and TPMJS. Their PNG dimensions changed as follows:

| TALA diagram | Previous pixels | Current pixels |
|---|---:|---:|
| Mocha SoC | 5,472 × 5,022 | 5,136 × 4,862 |
| Queue Workers | 4,982 × 5,668 | 5,906 × 4,498 |
| ROSS Overview | 3,602 × 7,738 | 3,148 × 8,258 |
| TPMJS (0.5×) | 3,226 × 5,238 | 3,184 × 3,950 |

TALA's new layout work changes optimization paths and geometry as well as runtime. In particular, TPMJS has about 26% fewer output pixels, which contributes to its PNG comparison. The other nine TALA diagrams are byte-identical to the previous reference.

## Interleaved old/new build comparison

A separate **12.4-minute run** (21:02:18–21:14:41 UTC) interleaved the previous and current D2 / Dagre and D2 / TALA binaries across all 13 diagrams and both formats. It used the same three warm-ups and 20 measured rounds per job: **2,080 measured invocations and 312 warm-ups**, all successful and stable. These samples are separate from the five-tool table above.

Real-world SVG latency fell **5.7% for both builds**. Primary PNG averages improved **1.3% for D2 / Dagre** and **2.2% for D2 / TALA**. The broad CLI gains are modest; larger gains are concentrated in particular diagrams.

Values below are changes in latency, with 95% paired-round bootstrap intervals in brackets. Negative means faster. The intervals describe sampling uncertainty within this desktop session; they do not cover all sources of machine or workload variation.

| Workload | Format | D2 / Dagre latency change | D2 / TALA latency change |
|---|---|---:|---:|
| Basic · 2 nodes | SVG | -0.9% [-3.6%, +1.7%] | -1.3% [-2.1%, +1.7%] |
| Basic · 2 nodes | PNG 2× | -3.6% [-6.6%, -1.6%] | +0.5% [-1.6%, +4.3%] |
| Basic · 10 nodes | SVG | -1.3% [-2.8%, +1.0%] | -2.4% [-6.7%, -0.4%] |
| Basic · 10 nodes | PNG 2× | -1.9% [-4.6%, +0.2%] | -0.7% [-3.7%, +2.4%] |
| Basic · 100 nodes | SVG | -3.5% [-7.1%, -1.2%] | -20.9% [-24.5%, -20.0%] |
| Basic · 100 nodes | PNG 2× | +12.8% [+10.6%, +14.4%] | -7.7% [-9.9%, -2.7%] |
| Real-world complex | SVG | -5.7% [-6.4%, -4.6%] | -5.7% [-7.8%, -4.8%] |
| Real-world complex | PNG 2× | -1.3% [-2.1%, -0.7%] | -2.2% [-3.2%, -1.1%] |
| TPMJS supplement | PNG 0.5× supplement | -17.7% [-18.7%, -16.1%] | -26.8% [-29.2%, -24.4%] |

The largest improvements include TPMJS SVG: D2 / Dagre **123.4 → 90.5 ms (−26.7%)**, TALA **3,572.5 → 2,675.1 ms (−25.1%)**. TPMJS PNG falls **367.3 → 302.3 ms (−17.7%)** for D2 and **3,795.3 → 2,780.0 ms (−26.8%)** for TALA. TALA's 100-node SVG also improves **135.9 → 107.5 ms (−20.9%)**.

**Two D2 PNG regressions persist within the same session:** the 100-node tree rises **464.2 → 523.5 ms (+12.8%)**, and ROSS rises **447.4 → 494.7 ms (+10.6%)**. Their outputs are byte-identical, with unchanged dimensions. These cumulative build comparisons establish the regressions but do not identify which individual commit caused them.

The TALA TPMJS gains include changed layout geometry; they are not an output-preserving renderer comparison. A bounded visual review of the four changed diagrams found no obvious clipping or missing major content. Queue Workers places some paired task labels closer together, without an obvious overlap.

[All group effects and paired intervals](paired-build-effects.csv) · [All per-diagram effects and paired intervals](paired-case-effects.csv). Ratios in these CSVs are previous/current, so values above 1 mean faster. Intervals use 2,000 bootstrap resamples of the 20 measured round indices, sharing each draw across both builds and all fixtures. Each draw recomputes per-fixture medians and their geometric-mean ratio; intervals are the linearly interpolated 2.5th and 97.5th percentiles. The deterministic seed is `4884683596465977979`, matching the harness's seed derivation for runner seed `20260905`. The corpus is fixed, warm-ups are excluded, and no outliers are removed.


## Builds and reproduction

| Build | Previous revision | Current revision |
|---|---|---|
| Public D2 / Dagre | `a825194903523c4409f4df7e7f4385efacb6deeb` | `c058268f661a124da15b409b0f907ec7b38f8228` |
| Private D2 / TALA | `3b6ba0e25fd36522021fa3b84cb4a8a08a651799` | `3f0a4a31a0aeadfc35b31bdb04def30982e2d304` |

The current revisions were the respective default-branch heads before measurement on September 7. TALA uses built-in layout with `--tala-seeds 1,2,3`, default seed concurrency, and unset `GOMAXPROCS`. Both CLIs were built from clean source with Go 1.27.0 and `CGO_ENABLED=0 GOTOOLCHAIN=local GOWORK=off go build -trimpath -ldflags='-s -w'`. Exact executable hashes are in each archive's environment metadata.

Public D2 includes the recent shared-pipeline optimizations and Dagro 0.2.1. This TALA staging revision still uses the older shared D2 pipeline and Dagro 0.2.0. They are separate CLI builds; comparing their times does not isolate layout choice.

Other runtimes are unchanged: Mermaid CLI 11.17.0 / Mermaid 11.17.2, Node 24.19.0, Chrome Headless Shell 152.0.7977.75, Graphviz 14.1.2, PlantUML 1.2026.8, and OpenJDK 21.0.10. Builds and setup occurred outside measurement.

Measured harness commit: `cdb6c2abe3946312e22bcc04bdb77654f4a01a95`, clean at the start of both runs. This publication updates documentation, reference data, and the public D2 source pin; the harness and corpus are unchanged. Using the repository version containing this example, follow the [optional TALA recipe](../../docs/CUSTOM-TOOLS.md#optional-d2--tala), then run:

```sh
env -u GOMAXPROCS ./make.sh --toolchain .tools-tala/toolchain.json \
  --tools d2-dagre d2-tala mermaid-dagre graphviz-dot plantuml-dot \
  --formats svg png --warmups 3 --repetitions 20 \
  --seed 20260905 --timeout 120 --bootstrap 2000 \
  --baseline d2-dagre --output results/reference-performance-tala
```

For the interleaved run, build the two previous revisions with the same flags, add their configurations as `d2-dagre-previous` and `d2-tala-previous`, and select those IDs alongside `d2-dagre` and `d2-tala`. Use a new output directory and the same sampling settings. The runner seed controls order separately from TALA's layout seeds.

## Data

[Complete five-tool run](https://github.com/d2lang/d2-benchmarks/raw/refs/heads/main/examples/2026-09-07-macos-m4-tala/reference-performance-tala-macos-m4-2026-09-07.tar.gz) · [SHA-256 checksum](reference-performance-tala-macos-m4-2026-09-07.tar.gz.sha256) · [Per-diagram timings](summary.csv) · [Historical per-diagram changes](comparison.csv)

[Complete interleaved old/new run](https://github.com/d2lang/d2-benchmarks/raw/refs/heads/main/examples/2026-09-07-macos-m4-tala/paired-d2-tala-refresh-macos-m4-2026-09-07.tar.gz) · [SHA-256 checksum](paired-d2-tala-refresh-macos-m4-2026-09-07.tar.gz.sha256) · [Interleaved per-diagram timings](paired-summary.csv)

Extract either archive and open `benchmark-run/index.html` for the rendered gallery, timing distributions, bootstrap intervals, and exact commands. Each archive retains raw records, inputs and licenses, rendered outputs, and an integrity manifest. Only local repository path prefixes are replaced with `${REPO}`; inputs and rendered bytes retain their hashes. No private TALA source or executable is included. The recorded runs reuse the unchanged public tools from `.tools-shell/`; standard setup uses `.tools/`.

Independent checks recomputed all medians, geometric means, published bootstrap intervals, and paired build effects from raw samples; verified complete randomized sampling, input and output hashes, dimensions, and unchanged tool controls; and checked the reference tables against those results. The archives include all 130 five-tool outputs and all 104 interleaved outputs. Unchanged binaries produced identical outputs across sessions.

See the [methodology](../../docs/METHODOLOGY.md), [corpus notes](../../corpus/README.md), and [setup details](../../docs/SETUP.md). The diagrams originated in D2, and tools produce different geometry. These runs do not establish performance on other machines or workloads.
