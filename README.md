# d2-benchmarks

**Results — September 5, 2026 · Apple M4 · SVG**

| Tool | Real-world SVG latency |
|---|---:|
| D2 / Dagre | 30.6 ms |
| Graphviz / dot | 77.5 ms |
| Mermaid / Dagre | 426.8 ms |
| PlantUML / Graphviz | 932.5 ms |

Latency is the geometric mean of ten per-diagram medians, with 20 measurements each. This previous reference measures real-world SVG only, in one active desktop session with uncontrolled background activity. [See the reference run and download its evidence](examples/2026-09-05-macos-m4-svg/README.md).

[![Validation and real-tool smoke tests](https://github.com/d2lang/d2-benchmarks/actions/workflows/ci.yml/badge.svg)](https://github.com/d2lang/d2-benchmarks/actions/workflows/ci.yml)

Reproducible, end-to-end CLI rendering benchmarks for **D2, Mermaid, Graphviz, and PlantUML**, covering SVG and PNG, basic diagrams at three sizes, and complex diagrams from real projects.

The suite measures the time to start a CLI, read a diagram, lay it out, render SVG or PNG, write the file, and exit. Results show latency, variation, and confidence intervals for each workload and format. Every run keeps its raw samples, versions, binary hashes, inputs, commands, and a gallery of actual outputs.

## Run it

Automatic setup supports macOS on Apple silicon and Ubuntu 24.04 on x86-64. It uses an installed Python 3.11.9+ or downloads a checksum-pinned Python if needed. See [setup details](docs/SETUP.md) for Linux browser libraries, download sizes, and using existing tools.

```sh
git clone https://github.com/d2lang/d2-benchmarks.git
cd d2-benchmarks
./make.sh
```

On the first run, `./make.sh` installs checksum-pinned tools into `.tools/`, builds a pinned public D2 revision, and leaves system packages alone. Later runs reuse the completed setup when its pins match. Mermaid uses Chrome Headless Shell 152.0.7977.75, matching the CLI's default `headless: "shell"` mode. Setup needs network access; benchmark commands use the local corpus and runtimes. Setup and compilation are outside the measured interval.

The runner prints the location of `results/<run>/index.html`. Open that file in your browser for the performance matrix, timing distributions, uncertainty intervals, and side-by-side diagrams. `report.md`, `summary.csv`, `summary.json`, and `raw.jsonl` are in the same directory. Reports are generated locally and need no server or external assets.

A complete run measures **13 diagrams × 4 tools × 2 formats**, with **3 excluded warm-ups and 20 measured repetitions** per job. Expect several minutes; the exact duration depends on your machine. Run this quick check first if desired:

```sh
./make.sh --nodes 2 --warmups 1 --repetitions 1 --output results/smoke
```

Smoke reports are labeled as such and are not performance evidence. Output directories must be new; an existing run is never overwritten.

To share a run, create a portable archive containing its raw records, inputs, rendered assets, integrity manifest, and regenerated reports. The direct Python commands below need Python 3.11.9+; see [setup details](docs/SETUP.md) to use the downloaded interpreter.

```sh
python3 scripts/export_run.py results/svg artifacts/svg.tar.gz
```

Optional `--redact-prefix '/absolute/local/repository=${REPO}'` replaces that host path prefix in metadata while retaining input/output bytes and hashes. Review custom configuration before publishing; prefix replacement does not remove arbitrary secrets. Keep generated runs outside Git history unless they are deliberately reviewed reference examples; see [contributing](CONTRIBUTING.md).

## Choose the workload

| Workload | Nodes and connections | Reported separately |
|---|---|---|
| Basic · 2 nodes | 2 nodes, 1 edge | SVG and PNG |
| Basic · 10 nodes | 10 nodes, 9 edges | SVG and PNG |
| Basic · 100 nodes | 100 nodes, 99 edges | SVG and PNG |
| Real-world complex | Ten diagrams with nesting, richer labels, and varied structure | Per-diagram results and SVG/PNG aggregates |

Basic diagrams are generated from the same balanced binary-tree pattern at each size, with plain labels and rectangular nodes. Each size has its own timing; the reports keep all workload families and formats separate.

```sh
# SVG only, all four public tools and all 13 diagrams
./make.sh --formats svg --output results/svg

# Basic scaling in both formats
./make.sh --nodes 2 10 100 --output results/basic

# Complex real-world diagrams in both formats
./make.sh --category real-world --output results/real-world

# Two tools, two diagrams, with more observations
./make.sh --tools d2-dagre graphviz-dot \
  --fixtures lion_reader_frontend tpmjs_architecture \
  --repetitions 30 --output results/focused

# Regenerate a report from its original samples; no rendering is repeated
python3 -m benchmarks report results/svg
```

Use `./make.sh --help` for toolchain, seed, timeout, baseline, and output options. A toolchain is an explicit JSON file of argument arrays, environment overrides, version commands, and provenance. To compare a local D2 build or an available TALA installation, copy `.tools/toolchain.json`, add or edit a D2 entry, and pass `--toolchain PATH --tools ...`; supplying a toolchain skips automatic setup. See [custom toolchains](docs/CUSTOM-TOOLS.md). TALA is optional and requires your own executable; no private source or access is required for the standard benchmark.

## What makes a comparison meaningful

- **Fresh process, warm filesystem.** Browser/JVM startup and shutdown are included. Warm-ups prepare filesystem caches; they do not keep a browser or JVM alive.
- **Serial randomized rounds.** Every selected job runs once per round, in a reproducible shuffled order. No benchmark commands overlap.
- **Raw observations retained.** No outliers are removed. Reports show medians, spread, confidence intervals, sample counts, failures, and incomplete runs. Aggregate comparisons use the same fixed set of diagrams.
- **Output checked.** The frozen corpus has source hashes, semantic mappings, provenance, and licenses. SVG identities and geometry are checked after timing; PNG structure and checksums are checked after timing. Invalid output is a failure.
- **Separate workloads.** Basic 2-, 10-, and 100-node timings are separate from each other and from real-world aggregates. SVG and PNG are never combined into one score.
- **Limits explained.** PNG uses 2× CSS-pixel density for all basic diagrams and nine real-world diagrams. TPMJS uses a separate 0.5× supplement and is excluded from the primary real-world PNG aggregate. Layouts, font embedding, styling, and resulting pixel counts differ.

The real-world diagrams originated in D2; the basic diagrams are generated trees. Together they cover specific workloads, not an unbiased sample of all graphs. PlantUML uses Graphviz internally; the comparison measures complete commands, not isolated layout algorithms. Read the [methodology](docs/METHODOLOGY.md) before interpreting rankings or publishing results.

Run on an idle, plugged-in machine with a stable power mode. Record relevant system settings. Repeat the entire experiment in independent sessions before making a performance claim. CI checks correctness with small real-tool renders; it does not gate changes on noisy hosted-runner timings.

## Corpus and development

The diagrams cover Jupyter infrastructure, a secure-enclave SoC, an inference target architecture, a rotor-dynamics package, a feed reader, and other substantial software systems. [Corpus provenance and translation notes](corpus/README.md) explain their origin and adaptations.

```sh
python3 -m unittest discover -s tests -v
python3 -m benchmarks validate
```

See [contributing](CONTRIBUTING.md) for adding a tool or diagram and submitting results. The harness is MIT-licensed; third-party diagrams and adapted translations retain their upstream licenses.
