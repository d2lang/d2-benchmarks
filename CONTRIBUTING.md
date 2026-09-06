# Contributing

Keep comparisons reproducible and reviewable. Run the unit tests and corpus validator before submitting changes. CI additionally renders a small fixture with the pinned real tools. Performance changes need raw evidence from stable local or dedicated machines; shared-runner timings are not a regression gate.

## Diagrams

Use documented real projects with a redistributable license and a pinned upstream revision. Include the original notice, context, and a clear list of adaptations. Remove fragile network image dependencies with attributed, explicitly described replacements. Do not choose examples solely because one tool wins.

Update all four source formats, semantic mappings, translation limitations, and manifest hashes together. Preserve objects, hierarchy, complete plain-text labels, edge multiplicity, endpoints, and visible arrow direction. Validate outputs and inspect the gallery at readable scale. A semantic check is necessary but does not prove visual quality.

## Runtimes and tooling

Pin versions and source revisions, verify downloaded artifacts against checksums, and update dependency locks deliberately. Test a fresh setup directory on the supported platform. A cache hit alone is not proof that installation works. Keep setup/build/download work outside timers. Add meaningful tests for process lifecycle, data validation, or statistical behavior that a change could break.

## Results

Keep raw observations and exact environment/provenance alongside summaries. State the goal, sampling plan, corpus, selected configurations, formats, density, machine/power settings, and whether background activity was controlled. Show failures and all matched cases. Do not discard outliers, mix machines/revisions into one session, publish smoke timings as a baseline, or attribute complete CLI differences solely to an internal layout algorithm.

`results/` is ignored by default because artifacts can be large and may contain local command paths. Review a run before sharing it. Store deliberately reviewed reference runs in clearly named `examples/` directories, with compact archives and checksums where appropriate, and explain any path redaction. This repository does not publish releases; identify harness versions by commit SHA and results by their measurement date. Retain input and output hashes when redacting host-specific prefixes. Never include private source, credentials, or unrelated system/environment dumps.

## Pull request descriptions

Use this structure, writing only below the AI heading and preserving the Human section:

```markdown
## Human

---

## AI

Describe the change and its validation here.
```
