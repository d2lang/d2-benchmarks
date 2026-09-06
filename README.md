# d2-benchmarks

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

Time to start the CLI, render a diagram, write the output, and exit—including browser or JVM startup. **Bold is fastest.** Each result uses 20 runs after 3 warm-ups. Basic rows are medians; real-world rows are geometric means of per-diagram medians.

The real-world set contains ten diagrams originally written in D2. PNG uses 2× density, except TPMJS at 0.5×, shown separately. Layouts and image dimensions differ between tools. These numbers come from one desktop session with uncontrolled background activity.

D2 / Dagre uses public D2 `a82519490352`; D2 / TALA uses the separate private staging build `3b6ba0e25fd3`. [Full results, versions, diagrams, and raw data](examples/2026-09-06-macos-m4-tala/README.md) · [Methodology](docs/METHODOLOGY.md).

## Run it

```sh
git clone https://github.com/d2lang/d2-benchmarks.git
cd d2-benchmarks
./make.sh
```

Supports macOS on Apple silicon and Ubuntu 24.04 on x86-64. The script downloads pinned tools on first use, then runs all 13 diagrams in SVG and PNG. Allow about 25 minutes, plus first-time setup. Open the printed `index.html` path for results and diagrams.

The default runs D2 / Dagre, Mermaid, Graphviz, and PlantUML. [Adding TALA](docs/CUSTOM-TOOLS.md#optional-d2--tala) requires access to the private staging build.

Use `./make.sh --help` to choose tools, formats, or diagrams. Run on an idle machine.

[Setup](docs/SETUP.md) · [Diagram sources](corpus/README.md) · [Contributing](CONTRIBUTING.md)
