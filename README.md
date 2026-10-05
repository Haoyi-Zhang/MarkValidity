# Replication package

This package reproduces the construct-validity study for code-watermark evaluation using public CPU resources and standard language runtimes.

## What is executed

The frozen pipeline builds:

- 12 independently implemented Python and JavaScript task families;
- complete finite-domain observations for 33,013 inputs per language;
- 72 effective semantic mutants and 504 bounded semantic-audit pairs;
- 1,296 structural-intervention observations;
- 76,032 attack-response observations;
- 38 context-deletion recomputations and 5,000 task-cluster bootstrap replicates;
- five declared decision functionals and exact attack-mixture stability calculations;
- a transfer audit over 24 public Python projects, 120 frozen modules, and 360 interventions;
- exact and empirical false-positive calculations; and
- seven scoring rules derived from SWEET, CodeIP, and SrcMarker on the frozen matrix; CodeIP is adapted to original indexed-survivor agreement, and the absent STONE naturalness component is not replaced.

This is not an external-system performance comparison. Pinned definitions and local mappings are recorded under `external-baselines/` and in `external_resources.csv`. The CodeIP-inspired rule requires all surviving original indexed bits to match, not equality with the original contiguous prefix; its historical `available_prefix` keys are unchanged. SWEET uses the declared analytic fair-bit null. The normalized source metric replaces both nonkeyword identifiers and numeric literals; its historical `identifier_normalized_similarity` key is retained. The intervention law and complete scheme-conditioned multipliers are defined in the supplement. External source code is not redistributed.

## Reproduce

From this directory:

```sh
PYTHONHASHSEED=1 PYTHONPATH=src python3 run_all.py --out results
python3 -m unittest discover -s tests -p 'test*.py' -v
python3 recheck.py results
```

Retained run results:

- 10 unit tests, zero failures;
- 900 independent reconstruction checks, zero failures;
- 149 nonvolatile result files identical under Python hash seeds 1 and 987;
- scientific-results SHA-256 `034812f8c869f902291b20a812761aeb97bf56f7e307dffe3ab59a885fd6fe48`.

`verify_release.py` checks the packaged result and document bindings. The retained receipts predate these definition and labeling corrections; document/source-bound receipts require regeneration before being treated as checks of the current files. The scientific outcome matrix is unchanged.
