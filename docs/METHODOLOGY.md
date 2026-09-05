# Methodology

## The question

How long does a local CLI take to produce a complete diagram file from source? The primary metric is elapsed wall-clock milliseconds from process creation through exit, including parsing, layout, rendering, file writing, and any child processes used by the CLI. The files are written through normal buffered filesystem I/O; this is not a durability or `fsync` benchmark.

The timer is Python's monotonic `perf_counter_ns`. Commands are argument arrays executed directly, without shell startup or shell calibration. Each invocation starts a new process group. A timeout kills that entire group and remains a recorded failure. Installation, compilation, translation, version probes, input copying, output validation, hashing, compression measurements, and reporting occur outside the timer.

This is a **warm-filesystem, fresh-process** experiment. Three warm-up invocations precede measurements for each job. They warm operating-system caches. They do not preserve application state, JVM JIT compilation, Chromium processes, or a diagram server across invocations. This workload is distinct from a persistent editor or a batched rendering service.

Mermaid CLI uses its own default `headless: "shell"` setting with the pinned Chrome Headless Shell executable. Setup checks that the browser variant matches that active CLI default. Browser variants can materially affect startup cost even when they report the same Chrome version.

## Experimental design

A job is one tool configuration × one diagram × one output format. A complete round runs each selected job once, serially. A seeded pseudorandom shuffle changes their order every round. The default is three warm-up rounds followed by twenty measured rounds. Fixed repetitions are chosen before the experiment; execution does not stop early when a desired ranking or confidence interval appears.

Run the experiment on a machine with minimal background work, a stable power mode, and enough memory to avoid swapping. Record power/CPU-affinity settings when relevant and repeat complete sessions. The runner records hardware/OS/Python information, available CPU affinity/governor information, timestamps, load averages, exact commands, tool version output, executable/entry-file hashes, setup provenance, corpus hashes, and harness file hashes. It does not change CPU governors, disable turbo, clear caches, request elevated priority, or silently tune the host. Those choices affect representativeness and must be deliberate.

The default includes all four publicly installable configurations. A custom toolchain may add another D2 build or TALA executable. State exactly which implementation is measured. An engine name alone is not a source revision or a guarantee that two D2 builds contain otherwise identical code.

## Correctness before speed

Inputs originate in D2's compiled semantic graph. Translations retain the semantic objects, immediate containment, edge endpoints and multiplicity, visible arrow direction, and plain-text labels. Immutable source hashes prevent silent edits. Sources and adaptations have upstream provenance and license notices.

The runner validates every retained output after its process exits. SVG checks inspect object/edge identity and finite geometry using the format's renderer identifiers. PNG checks verify signature, chunk boundaries, CRCs, required chunks, and dimensions. PNG checks do not prove pixel-level visual correctness; inspect the gallery, particularly after updating a renderer. Validation work is untimed but can affect caches between commands, so the same validation procedure is used throughout a session.

A command returning zero with an invalid or missing output is a failure. Warm-up failures, measured failures, timeouts, and interrupted sessions remain visible. No failed attempt is replaced by a retry. Per-job successful-sample statistics are labeled with their denominator; aggregate rankings require complete successful comparable jobs and a completed session. A tool that fails the difficult cases cannot obtain a better score by dropping them.

Output hash stability is reported, not assumed. Nondeterministic identifiers or metadata can change bytes without changing appearance; investigate differences before attributing them to layout or declaring them harmless.

## Statistics and presentation

Each job's headline is the sample median. Reports preserve the full distribution and show sample counts and spread; they do not discard statistical outliers or present a small-sample p99 as a reliable tail estimate.

Deterministic percentile bootstrap intervals are **95% within-session sampling intervals**. For aggregate ratios, complete round IDs are resampled jointly across the fixed corpus and compared using the resampled medians. This retains shared within-round variation between tools. The corpus itself is not resampled. These intervals do not cover uncertainty about other machines, system configurations, independent sessions, all possible diagrams, or temporal correlations between neighboring rounds. Twenty observations remain a modest sample; narrow intervals do not remove systematic bias.

Aggregate latency is the geometric mean of per-diagram median latencies. Ratios compare the same diagrams with equal weight on the logarithmic scale. Per-diagram results remain primary evidence: the aggregate can hide an important outlier. A ratio of 2× means one configuration takes twice as long on that matched aggregate; it does not mean every diagram takes twice as long. Rankings are withheld when the required cases are incomplete or unsuccessful.

Reports include Markdown, JSON, CSV, local HTML, actual SVG/PNG artifacts, and raw JSONL observations. Regenerating a report never reruns the commands. Keep machine, corpus, toolchain, and sampling settings alongside any published numbers. Compare independent runs on the same machine before claiming a regression, and compare several machines before claiming a general advantage. GitHub-hosted CI is a correctness check, not a stable performance lab.

## Raster density and assets

Nine primary PNG cases use 2× CSS-pixel density: D2 `--scale 1`, Mermaid `-s 2`, Graphviz `-Gdpi=192`, PlantUML `-Sdpi=192`. Graphviz's SVG point dimensions convert at 96 CSS pixels per inch / 72 points per inch. TPMJS exceeds D2's normal-density raster pixel limit, so its PNG uses a separate 0.5× supplement: D2 `--scale 0.25`, Mermaid `-s 0.5`, and Graphviz/PlantUML DPI 48. It is explicitly excluded from the primary PNG aggregate rather than silently downscaled only for one tool.

PlantUML's image side limit is raised from 4096 to 32768 pixels to retain complete large diagrams. Source metadata remains enabled. Outputs are not minified or resized after rendering. SVG gzip size is measured independently per original file at level 9 with a fixed gzip timestamp, outside the timer. PNG byte counts refer to original files.

Matching density does not equal matching pixel count. D2 grid/position constraints, themes, shapes, Markdown typesetting, fonts, padding, routes, and some styles differ in the translations. D2 SVG embeds font subsets; other SVGs generally depend on viewer fonts. D2 PNG can append link/tooltip information for some sources. PlantUML generates its own graph and runs Graphviz internally, so subtracting direct Graphviz time from PlantUML time cannot isolate JVM overhead. The gallery and byte/pixel tables help readers see these differences.

## References

The design uses repeated observations, explicit warm-up/cache behavior, machine metadata, and transparent distributions described by [pyperf's reproducibility guidance](https://pyperf.readthedocs.io/en/latest/run_benchmark.html), [pyperf's system guidance](https://pyperf.readthedocs.io/en/latest/system.html), [Hyperfine's warm-up and export documentation](https://github.com/sharkdp/hyperfine), and [Google Benchmark's repetitions and statistics guide](https://google.github.io/benchmark/user_guide.html). The small standard-library runner adds the suite's randomized rounds, per-output validation, and artifact bookkeeping.

Tool semantics: [Graphviz CLI](https://graphviz.org/doc/info/command.html), [Graphviz DPI](https://graphviz.org/docs/attrs/dpi/), [PlantUML CLI](https://plantuml.com/command-line), and [PlantUML image limits](https://plantuml.com/faq).
