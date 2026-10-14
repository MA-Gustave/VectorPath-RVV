# Performance results and limitations

## Historical MethodLab evidence (supplied snapshot)

| Experiment | Baseline | Reported ratio |
| --- | --- | --- |
| 2026-10-10, three-hour native engine comparison | `upstream_vls256`, matched workload/trial | E14 DOM **1.473×** geometric mean |
| 2026-10-11, eight-hour native stage profile | `upstream_vls256`, matched stage workload | E14 DOM **1.502×**; Stage 1 **1.601×**; Stage 2 **1.298×** |

These results refer to experimental versions and specific controlled conditions, not all JSON inputs or machines. They must not be represented as fresh benchmarks of a newly named repository. E14 can regress on some inputs; correctness coverage and hardware/compiler choices affect interpretation. The supplied narrative also mentions approximately **65%** improvement for later code; this specific figure has not been independently verified in this packaging process.

For source measurements and limitations consult the separately maintained MethodLab at `https://github.com/MA-Gustave/vla-methodlab`, particularly `docs/METHODOLOGY.md` and `docs/results/2026-10-11-stage-profile-8h.md`.
