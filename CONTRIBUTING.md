# Contributing

Keep comparisons reproducible and reviewable. Run the unit tests and corpus validator before submitting changes. CI additionally renders the basic cases and a real-world fixture with the pinned real tools. Performance changes need raw evidence from stable local or dedicated machines; shared-runner timings are not a regression gate.

## Diagrams

The corpus has two roles: basic 2-, 10-, and 100-node trees expose size-dependent CLI latency with minimal diagram features, while real-world complex diagrams exercise richer structures. Keep basic fixtures deterministic, with matching labels, shapes, direction, and topology in every source format. Do not add tool-specific styling or containers to the basic cases. Treat a change of topology as a new workload, not an interchangeable node-count sample.

For real-world fixtures, use documented projects with a redistributable license and a pinned upstream revision. Include the original notice, context, and a clear list of adaptations. Remove fragile network image dependencies with attributed, explicitly described replacements. Do not choose examples solely because one tool wins.

Update all four source formats, semantic mappings, translation limitations, and manifest hashes together. Preserve objects, hierarchy, complete plain-text labels, edge multiplicity, endpoints, and visible arrow direction. Validate outputs and inspect the gallery at readable scale. A semantic check is necessary but does not prove visual quality.

## Runtimes and tooling

Pin versions and source revisions, verify downloaded artifacts against checksums, and update dependency locks deliberately. Test a fresh setup directory on the supported platform. A cache hit alone is not proof that installation works. Keep setup/build/download work outside timers. Add meaningful tests for process lifecycle, data validation, or statistical behavior that a change could break.

## Results

Keep raw observations and exact environment/provenance alongside summaries. State the goal, sampling plan, corpus, selected configurations, formats, density, machine/power settings, and whether background activity was controlled. Show failures and all matched cases. Do not discard outliers, mix machines/revisions into one session, publish smoke timings as a baseline, or attribute complete CLI differences solely to an internal layout algorithm.

This suite measures rendering performance. Report latency and its distribution separately for SVG and PNG, for each basic node count, and for the real-world complex corpus. Use 2× density for all PNG cases. Do not create a blended score across these workloads or add file-size/compression comparisons as benchmark metrics. Retain output hashes, dimensions, and viewable artifacts as correctness evidence. A published matrix must identify unmeasured cells rather than filling them from a different session or silently reusing an older corpus.

Keep only the current published run in `reference/`; replace it when refreshing the README results. Do not accumulate dated archives or change reports. Local runs stay in ignored `results/`. Review data before sharing it, include a checksum, and retain input/output hashes and exact build metadata. Explain path redaction and exclude private source, credentials, and unrelated environment data.

## Pull request descriptions

Use this structure, writing only below the AI heading and preserving the Human section:

```markdown
## Human

---

## AI

Describe the change and its validation here.
```
