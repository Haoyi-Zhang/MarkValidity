# Execution environment

The benchmark is designed for a public CPU environment. It uses the Python standard library for the core analysis and a JavaScript runtime for the independent language implementations. No GPU, model service, learned-model inference, training, private dataset, or proprietary dependency is required.

Canonical execution:

```sh
PYTHONHASHSEED=1 PYTHONPATH=src python3 run_all.py --out results
python3 -m unittest discover -s tests -p 'test*.py' -v
python3 recheck.py --results results
```

The frozen environment record is `results/environment.json`, SHA-256 `97516740745c00a6eba6068cdeff2976f39a1fe93046ffc74d8603eb6ba1a644`.

The external evaluation-protocol replay is formula-level. Complete SWEET, CodeIP, SrcMarker, and STONE system execution is intentionally outside the frozen resource contract because those pipelines require model generation, trained checkpoints, CUDA, or an unavailable naturalness component. This exclusion is part of the claim boundary, not an unexecuted promise.

# Current candidate check (2026-10-14)

The separate current receipt is `results/evidence-audit-20261014-current/receipt.json`.
Actual runtimes were CPython 3.12.14 and Node v24.19.0 on Windows 11
(10.0.28000). No installation was performed; the audit imports only reviewed
local modules and runtime standard libraries. The current 32-unit and three
reporting tests are distinct from the older Ubuntu evidence. The current
native scope is 24 owned references, 72 existing mutants, and 72 carrier-only
no-ops, not a regeneration of all historical transformations or the state matrix.
