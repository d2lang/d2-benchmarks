# Diagram licenses

The three generated basic fixtures and their translated derivatives are original benchmark inputs, copyright (c) 2026 D2 Authors, under the [MIT license](licenses/basic_MIT_LICENSE). They have no third-party upstream source.

The ten real-world diagrams and their translated derivatives retain their upstream licenses; the benchmark implementation license does not replace these licenses. Copyright notices and full license texts are included unchanged. Every generated translation is a modification of the corresponding D2 diagram, with changes described in [TRANSLATIONS.md](TRANSLATIONS.md).

| Fixture and derivatives | License | Retained license / attribution |
|---|---|---|
| Fulcro RAD architecture | MIT | [fulcro_rad_LICENSE](licenses/fulcro_rad_LICENSE) |
| Jupyter AWS EKS infrastructure | MIT | [jupyter_aws_eks_LICENSE](licenses/jupyter_aws_eks_LICENSE) |
| Jupyter Kubernetes OIDC access flow | MIT | [jupyter_k8s_oidc_LICENSE](licenses/jupyter_k8s_oidc_LICENSE) |
| Ouroboros Leios simulator components | Apache-2.0 | [leios_simulator_LICENSE](licenses/leios_simulator_LICENSE) |
| Lion Reader frontend data flow | MIT | [lion_reader_frontend_LICENSE](licenses/lion_reader_frontend_LICENSE) |
| Mocha secure-enclave SoC | Apache-2.0 | [mocha_soc_REUSE.toml](licenses/mocha_soc_REUSE.toml); [mocha_soc_Apache-2.0.txt](licenses/mocha_soc_Apache-2.0.txt) |
| Go Queue multi-service worker architecture | MIT | [queue_workers_LICENSE](licenses/queue_workers_LICENSE) |
| ROSS package overview | Apache-2.0 | [ross_overview_LICENSE.md](licenses/ross_overview_LICENSE.md) |
| Spyre encoder inference target design | Apache-2.0 | [spyre_encoder_LICENSE](licenses/spyre_encoder_LICENSE) |
| TPMJS platform architecture v1 | MIT | [tpmjs_architecture_LICENSE](licenses/tpmjs_architecture_LICENSE) |

For Mocha, `REUSE.toml` explicitly assigns Apache-2.0 and the lowRISC Contributors (COSMIC project) copyright statement to `doc/**`; both that attribution and the Apache license are retained.

Pinned Apache-licensed source trees were checked for an applicable `NOTICE`, `NOTICE.txt` or `NOTICE.md` at the source-file directory or an ancestor. None was present. The evidence is recorded in `source-verification.json`. Public source links and exact revisions are listed in [PROVENANCE.md](PROVENANCE.md).
