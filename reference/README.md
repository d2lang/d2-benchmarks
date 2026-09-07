# Reference data

Data behind the [README results](../README.md), measured September 7, 2026 UTC on an Apple M4 with 16 GiB RAM.

[Download the run](https://github.com/d2lang/d2-benchmarks/raw/refs/heads/main/reference/run.tar.gz) · [SHA-256 checksum](run.tar.gz.sha256) · [Per-diagram timings](summary.csv)

Extract the archive and open `benchmark-run/index.html` for all 130 rendered outputs, raw samples, confidence intervals, exact commands, and build metadata. All 2,600 measured invocations and 390 warm-ups succeeded, with stable output hashes. Background activity was uncontrolled.

The archive contains no private TALA source or executable. Local repository paths are replaced with `${REPO}`; input and rendered bytes retain their original hashes.

To rerun, follow the [TALA setup](../docs/CUSTOM-TOOLS.md#optional-d2--tala), then:

```sh
env -u GOMAXPROCS ./make.sh --toolchain .tools-tala/toolchain.json \
  --tools d2-dagre d2-tala mermaid-dagre graphviz-dot plantuml-dot \
  --formats svg png --warmups 3 --repetitions 20 \
  --seed 20260905 --output results/reference
```
