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
- an independent replay of seven public evaluation functionals from SWEET, CodeIP, and SrcMarker on the same frozen outcome matrix, with the unavailable STONE naturalness component retained as a declared construct mismatch.

The replay is not a performance comparison of the external watermark systems. Their complete pipelines require learned-model generation, trained checkpoints, or CUDA outside the frozen CPU-only no-model contract. Only their public scoring definitions are independently reimplemented and applied to common preserved outcomes. Source revisions, locators, licenses, and execution boundaries are recorded under `external-baselines/` and in `external_resources.csv`; external source code is not redistributed.

## Reproduce

From this directory:

```sh
PYTHONHASHSEED=1 PYTHONPATH=src python3 run_all.py --out results
python3 -m unittest discover -s tests -p 'test*.py' -v
python3 recheck.py results
```

Expected release results:

- 10 unit tests, zero failures;
- 900 independent reconstruction checks, zero failures;
- 149 nonvolatile result files identical under Python hash seeds 1 and 987;
- scientific-results SHA-256 `034812f8c869f902291b20a812761aeb97bf56f7e307dffe3ab59a885fd6fe48`.

`verify_release.py` additionally checks the four-entry project root, result and document hashes, the single retained submission rendering, one-author-per-line title metadata, pagination, fonts, all 82 bibliographic evidence objects, the three-round audit of all 88 local citation positions, external protocol provenance, absence of generated debris, and release-manifest coverage.
