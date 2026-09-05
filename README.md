# d2-benchmarks

[![Validation and real-tool smoke tests](https://github.com/d2lang/d2-benchmarks/actions/workflows/ci.yml/badge.svg)](https://github.com/d2lang/d2-benchmarks/actions/workflows/ci.yml)

Reproducible, end-to-end CLI benchmarks for **D2, Mermaid, Graphviz, and PlantUML**, using ten substantial diagrams from real projects.

The suite measures the time to start a CLI, read a diagram, lay it out, render SVG or PNG, write the file, and exit. It also measures asset sizes and provides a gallery of the actual outputs. Every run keeps its raw samples, versions, binary hashes, inputs, and commands.

## Run it

Prerequisite: **Python 3.12 or newer** (3.11.9+ also works). The automatic setup supports macOS on Apple silicon and Ubuntu 24.04 on x86-64. See [setup details](docs/SETUP.md) for Linux browser libraries, download sizes, and using existing tools.

```sh
git clone https://github.com/d2lang/d2-benchmarks.git
cd d2-benchmarks
python3 scripts/setup.py
python3 -m benchmarks run
```

Setup installs checksum-pinned tools into `.tools/`, builds a pinned public D2 revision, and leaves system packages alone. It needs network access; benchmark commands use the local corpus and runtimes. Setup and compilation are outside the measured interval.

The runner prints the location of `results/<run>/index.html`. Open that file in your browser for timing distributions, uncertainty intervals, asset sizes, and side-by-side diagrams. `report.md`, `summary.csv`, `summary.json`, and `raw.jsonl` are in the same directory. Reports are generated locally and need no server or external assets.

A complete run has **3 excluded warm-ups and 20 measured repetitions** per tool, diagram, and format. Expect several minutes; the exact duration depends on your machine. Run this quick check first if desired:

```sh
python3 -m benchmarks doctor
python3 -m benchmarks validate
python3 -m benchmarks run --fixtures lion_reader_frontend --warmups 1 --repetitions 1 --output results/smoke
```

Smoke reports are labeled as such and are not performance evidence. Output directories must be new; an existing run is never overwritten.

To share a run, create a portable archive containing its raw records, inputs, rendered assets, integrity manifest, and regenerated reports:

```sh
python3 scripts/export_run.py results/svg artifacts/svg.tar.gz
```

Optional `--redact-prefix '/absolute/local/repository=${REPO}'` replaces that host path prefix in metadata while retaining input/output bytes and hashes. Review custom configuration before publishing; prefix replacement does not remove arbitrary secrets. Generated archives belong outside Git history.

## Choose the workload

```sh
# SVG only, all four public tools and all ten diagrams
python3 -m benchmarks run --formats svg --output results/svg

# Two tools, two diagrams, with more observations
python3 -m benchmarks run --tools d2-dagre graphviz-dot \
  --fixtures lion_reader_frontend tpmjs_architecture \
  --repetitions 30 --output results/focused

# Regenerate a report from its original samples; no rendering is repeated
python3 -m benchmarks report results/svg
```

Use `python3 -m benchmarks run --help` for toolchain, seed, timeout, baseline, and output options. A toolchain is an explicit JSON file of argument arrays, environment overrides, version commands, and provenance. To compare a local D2 build or an available TALA installation, copy `.tools/toolchain.json`, add or edit a D2 entry, and pass `--toolchain PATH --tools ...`. See [custom toolchains](docs/CUSTOM-TOOLS.md). TALA is optional and requires your own executable; no private source or access is required for the standard benchmark.

## What makes a comparison meaningful

- **Fresh process, warm filesystem.** Browser/JVM startup and shutdown are included. Warm-ups prepare filesystem caches; they do not keep a browser or JVM alive.
- **Serial randomized rounds.** Every selected job runs once per round, in a reproducible shuffled order. No benchmark commands overlap.
- **Raw observations retained.** No outliers are removed. Reports show medians, spread, confidence intervals, sample counts, failures, and incomplete runs. Aggregate comparisons use the same fixed set of diagrams.
- **Output checked.** The frozen corpus has source hashes, semantic mappings, provenance, and licenses. SVG identities and geometry are checked after timing; PNG structure and checksums are checked after timing. Invalid output is a failure.
- **Limits explained.** PNG uses 2× CSS-pixel density for nine diagrams. TPMJS uses a separate 0.5× supplement and is excluded from the primary PNG aggregate. Layouts, font embedding, styling, and resulting pixel counts differ.

These are D2-authored diagrams, so the corpus is not an unbiased sample of all graph workloads. PlantUML uses Graphviz internally; the comparison measures complete commands, not isolated layout algorithms. Smaller assets do not imply equal appearance or portability. Read the [methodology](docs/METHODOLOGY.md) before interpreting rankings or publishing results.

Run on an idle, plugged-in machine with a stable power mode. Record relevant system settings. Repeat the entire experiment in independent sessions before making a performance claim. CI checks correctness with small real-tool renders; it does not gate changes on noisy hosted-runner timings.

## Corpus and development

The diagrams cover Jupyter infrastructure, a secure-enclave SoC, an inference target architecture, a rotor-dynamics package, a feed reader, and other substantial software systems. [Corpus provenance and translation notes](corpus/README.md) explain their origin and adaptations.

```sh
python3 -m unittest discover -s tests -v
python3 -m benchmarks validate
```

See [contributing](CONTRIBUTING.md) for adding a tool or diagram and submitting results. The harness is MIT-licensed; third-party diagrams and adapted translations retain their upstream licenses.
