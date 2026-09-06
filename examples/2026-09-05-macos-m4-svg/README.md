# Reference run: ten SVG diagrams on an Apple M4

An example of the suite's output, measured September 5, 2026. This is one active desktop session, with uncontrolled background activity; it is not a cross-machine ranking. All 800 measured invocations and 120 excluded warm-ups succeeded. All 40 jobs produced identical output hashes across their 20 measured samples.

[Download the complete run](https://github.com/d2lang/d2-benchmarks/raw/refs/heads/main/examples/2026-09-05-macos-m4-svg/reference-svg-macos-m4-2026-09-05.tar.gz) · [SHA-256 checksum](reference-svg-macos-m4-2026-09-05.tar.gz.sha256)

The archive is also included in this directory when you clone the repository. Extract it and open `benchmark-run/index.html` locally. It includes the interactive comparisons, per-diagram distributions and 95% bootstrap intervals, raw records, CSV/JSON/Markdown summaries, original inputs and licenses, SVGs, and an integrity manifest. Local repository path prefixes are replaced with `${REPO}` in metadata; input/output bytes and hashes are unchanged.

| Tool | SVG latency | Total SVG bytes | Total SVG gzip-9 bytes |
|---|---:|---:|---:|
| D2 / Dagre | 30.6 ms | 571,234 | 201,206 |
| Graphviz / dot | 77.5 ms | 328,419 | 61,394 |
| Mermaid / Dagre | 426.8 ms | 656,710 | 94,024 |
| PlantUML / Graphviz | 932.5 ms | 355,876 | 90,871 |

Latency is the geometric mean of ten per-diagram medians, with 20 measurements per median. Sizes sum ten complete files, independently compressed at gzip level 9. The archive has the per-case evidence and matched-round bootstrap intervals. Font embedding, styling, geometry, and metadata differ. This example measures SVG only; the default runner also measures primary 2× PNG and the separately reported TPMJS 0.5× supplement.

## Reproduce this example

Benchmark harness: `a2dae1e1c778edfe9fa8e4d3299ca6a89c99722d`. Public D2 source: `a825194903523c4409f4df7e7f4385efacb6deeb`. Other runtimes: Mermaid CLI 11.17.0 / Mermaid 11.17.2, Node 24.19.0, Chrome Headless Shell 152.0.7977.75, Graphviz 14.1.2, PlantUML 1.2026.8, OpenJDK 21.0.10.

```sh
git checkout a2dae1e1c778edfe9fa8e4d3299ca6a89c99722d
python3 scripts/setup.py
python3 -m benchmarks run --formats svg --warmups 3 --repetitions 20 \
  --seed 20260905 --output results/reference-svg
```

The archive records macOS, hardware, runtime/binary hashes, exact command arrays, and the original start/end times. Different operating systems or host fonts need not produce identical assets. See the [methodology](../../docs/METHODOLOGY.md) and [setup notes](../../docs/SETUP.md).
