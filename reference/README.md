# Reference data

Data behind the [README results](../README.md), measured September 7, 2026 UTC on an Apple M4 with 16 GiB RAM.

[Download the run](https://github.com/d2lang/d2-benchmarks/raw/refs/heads/main/reference/run.tar.gz) · [SHA-256 checksum](run.tar.gz.sha256) · [Per-diagram timings](summary.csv)

Extract the archive and open `benchmark-run/index.html` for the 130 cases, rendered outputs, raw samples, confidence intervals, exact commands, and build metadata. All 2,600 measured invocations and 390 warm-ups exited successfully. Visual review rejected Mermaid's TPMJS PNGs: both observed variants omit lower content, affecting all 20 measurements and 3 warm-ups for that case. Its aggregate is unavailable. The original observations are unchanged; `review.json` records the rejected hashes and reasons, with a diagnostic reproduction beside the retained outputs.

All PNG cases use 2× density. D2 output hashes were stable throughout. Background activity was uncontrolled.

Both D2 layouts use the same public build; TALA uses seeds `1,2,3`. Local repository paths are replaced with `${REPO}`; input and rendered bytes retain their original hashes.

To rerun with the pinned tools:

```sh
env -u GOMAXPROCS ./make.sh --seed 20260905 --output results/reference
```

See [setup](../docs/SETUP.md) for prerequisites and options.
