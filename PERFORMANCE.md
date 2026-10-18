# Performance results and limitations

## Historical MethodLab evidence (supplied snapshot)

| Experiment | Baseline | Reported ratio |
| --- | --- | --- |
| 2026-10-10, three-hour native engine comparison | `upstream_vls256`, matched workload/trial | E14 DOM **1.473×** geometric mean |
| 2026-10-11, eight-hour native stage profile | `upstream_vls256`, matched stage workload | E14 DOM **1.502×**; Stage 1 **1.601×**; Stage 2 **1.298×** |

These results refer to experimental versions and specific controlled conditions, not all JSON inputs or machines. They must not be represented as fresh benchmarks of a newly named repository. E14 can regress on some inputs; correctness coverage and hardware/compiler choices affect interpretation. The supplied narrative also mentions approximately **65%** improvement for later code; this specific figure has not been independently verified in this packaging process.

For source measurements and limitations consult the separately maintained MethodLab at `https://github.com/MA-Gustave/vla-methodlab`, particularly `docs/METHODOLOGY.md` and `docs/results/2026-10-11-stage-profile-8h.md`.

## 2026-10-18 VectorPath A2 stable release candidate

The default profile was consolidated from the MethodLab *measured* A2 level 2 / 16 KiB / packed-off configurations. **No new native speedup has yet been measured on the source-changed release candidate.** Test104's historical 18 public JSON DOM mean ratio versus official simdjson 5.0.4 **fallback** was about 1.894x EPCC and 1.595x Cloud-V. These figures do not represent the speedup of the two optional Stage2 changes. Test103/104 found large isolated benefits on dense synthetic escape fixtures; Test104 found small opposite-direction shifts on public JSON across EPCC and Cloud-V, so both Stage 2 experiments remain disabled by default.

See `docs/VECTORPATH_RC_VALIDATION.md` for correctness, reproducibility, and release criteria, and `README-VECTORPATH-RELEASE-CANDIDATE.md` for configuration and limitations. Never present the public JSON geometric mean as a universal application speedup or as a matched-RVV comparison to official fallback.
