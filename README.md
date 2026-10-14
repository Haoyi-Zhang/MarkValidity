# Replication package

This package reproduces the construct-validity study for code-watermark evaluation using public CPU resources and standard language runtimes.

## What is executed

The frozen pipeline builds:

- 12 independently implemented Python and JavaScript task families;
- complete finite-domain observations for 33,013 inputs per language;
- 72 effective semantic mutants and 504 bounded semantic-audit pairs;
- 1,296 structural-intervention observations;
- 76,032 indexed-carrier-state attack-response observations, computed without rendering or executing each row;
- 38 context-deletion recomputations and 5,000 task-cluster bootstrap replicates;
- five declared decision functionals and exact attack-mixture stability calculations;
- a transfer audit over 24 public Python projects, 120 frozen modules, and 360 interventions;
- exact and empirical false-positive calculations, including 30,000 rendered snippets checked by regex extraction rather than a language parser; and
- seven scoring rules derived from SWEET, CodeIP, and SrcMarker on the frozen matrix; CodeIP is adapted to original indexed-survivor agreement, and the absent STONE naturalness component is not replaced.

This is not an external-system performance comparison. Pinned definitions and local mappings are recorded under `external-baselines/` and in `external_resources.csv`. The CodeIP-inspired rule requires all surviving original indexed bits to match, accepting zero survivors vacuously, not equality with the original contiguous prefix; its historical `available_prefix` keys are unchanged. SWEET uses the declared analytic fair-bit null. The normalized source metric replaces both nonkeyword identifiers and numeric literals; its historical `identifier_normalized_similarity` key is retained. The intervention law and complete scheme-conditioned multipliers are defined in the supplement. External source code is not redistributed.

## Joint-evidence diagnostic

`check_joint_evidence.py` is a separate data-only analysis of the retained
`results/current/results/` tables. It does not import or run carrier generation,
attacks, source extraction, or upstream code. Run it with the selected Python
environment using `python -B -S check_joint_evidence.py --out .joint-audit-fresh`.
The output must be a new directory disjoint from the inputs. Omitting `--out`
selects a fresh UTC-named directory; it no longer overwrites the historical
`results/joint_diagnostic/`. It writes stratum/mixture CSVs and a source-bound receipt;
the historical observations and manifests remain unchanged.

The 504 semantic checks contain 72 carrier-only rows and 432 rows that link to
dense configurations under the reviewed producer's payload-zero/full-severity
mapping. Coverage is 432/76,032 = 1/176, leaving 75,600 unknown labels. The mapping
is conditional: dense rows contain no source hash or source-extraction result.
All 432 linked labels pass and 122 also have a positive state-model decision.
Sharp bounds over missing binary-label completions identify no strict
validity-conditioned winner under any of the three mixtures. Actual source-valid
detection is not identified by those model bounds; the recorded evidence alone
leaves it in [0,1]. Unknown labels are neither failed nor successful trials.

`src/covewm/joint_bounds.py` supplies the one-pass closed-form bound, including
an optional same-universe validity-count marginal and analytical endpoint
completion counts. The separate feasible-table enumeration in the diagnostic
uses the same information and agrees on all 198 strata; no accuracy or timing
gain is claimed. `tests/test_joint_bounds.py` checks all 1,554 nonempty partial
binary tables through four rows and all 21,834 table/marginal combinations
against full missing-label enumeration. This is a bounded method diagnostic,
not new evidence of external system defects or upstream reproduction.

Response-curve Clopper--Pearson fields retain their historical values, but are
now explicitly interpreted as homogeneous independent-Bernoulli reference-model
intervals. They do not provide exact coverage for the deterministic, heterogeneous
indexed-state enumeration. The empirical null experiments have a separate trial
model. Current local discovery contains 32 unit tests plus three reporting
regressions; historical Ubuntu test counts remain historical.

The retained `results/current/results/derived/duplication_sensitivity.csv` contains three separate carrier-specific weighting witnesses, not one common reweighted comparison. Lexical repeats `normalize`, structural repeats `rename`, and hybrid repeats `strip`; each favored family occurs 20 times and the other four destructive families once. The duplicated micro-mean is `(5 * macro + 19 * favored_rate) / 24`; every family mean and the equal-family macro-mean remain unchanged.

In `decision_functional_sensitivity.csv`, the legacy `rank` column is deterministic display order: descending score, then alphabetical carrier name for equal values. It does not imply a strict preference between tied scores. The threshold-share functional ties lexical and structural at `2/5`, in display positions 2 and 3, below the unique hybrid score `3/5`.

## Reproduce

From this directory:

```sh
PYTHONHASHSEED=1 PYTHONPATH=src python3 run_all.py --out results
python3 -m unittest discover -s tests -p 'test*.py' -v
python3 recheck.py --results results
```

Retained original run results (not measurements of the current Windows repair campaign):

- 10 unit tests, zero failures;
- 900 independent reconstruction checks, zero failures;
- 149 nonvolatile result files identical under Python hash seeds 1 and 987;
- scientific-results SHA-256 `034812f8c869f902291b20a812761aeb97bf56f7e307dffe3ab59a885fd6fe48`.

The earlier retained Ubuntu run is in `results/current/`: thirteen unit tests,
900 reconstruction checks, and 504 semantic-audit pairs complete without
failures, ineffective mutants, or cross-language disagreement. This directory
contains regenerated observations and the accompanying command output. The
earlier ten-test run above is a separate historical record. To reconstruct the
current rows, run `python3 recheck.py --results results/current/results`.

The retained Ubuntu unit suite contains 13 tests. It additionally checks detector accounting
for one-shot iterators, Unicode byte/character offset alignment in the token-based
local rename, and rejection of failed semantic premises before diagnostic AUCs.
The rename deliberately skips nested functions, classes, and lambdas and is not a
general binding-preserving transformation. The source token metrics retain the
frozen regex profile (including its literal/comment limitations), not a full lexer.
The generator writes raw semantic tables before its validation gate, and a rejected
run must not be interpreted as a completed scientific result. Reconstruction can
read an external `--results` directory while resolving the licensed corpus beside
the checker source. Run outputs and local repair logs are not deployment evidence.

Six additional self-contained tests in `tests/test_metric_streams.py` check the
seven source fields against hand-specified tokens/profiles and a test-local
reference, plus helper compatibility and token-call counts (not elapsed time).
Run `python -B -S -m unittest discover -s tests -p test_metric_streams.py -v`
from the artifact root. `source_metrics` reuses its two regex token streams for
identifier, normalized-token, and control features; source-taking helpers and
the separate JavaScript syntax-profile path remain. Current discovery contains
19 tests at that earlier repair stage; the historical results and source/result manifests are not new
measurements of this private change. No speedup or broader metric validity is
claimed.

## Current non-destructive evidence audit

Run from the artifact root with Python >=3.11 and Node >=18 already available:

```sh
export COVEWM_RESULTS="$PWD/results/current/results"
python -B -S -m unittest discover -s tests -p 'test*.py' -v
python -B -S -m unittest discover -s regressions -p 'test*.py' -v
python -B -S validate_evidence.py --results "$COVEWM_RESULTS" --out .evidence-audit-fresh
```

All outputs must be fresh and disjoint from the retained input directory.
`make audit-evidence` selects `.evidence-audit`; it refuses to replace that
directory on a repeated invocation. The default scientific workflow now includes
the three reporting checks and this audit, against the freshly selected
`COVEWM_RESULTS`, rather than silently reading an older result set.

The 2026-10-14 Windows candidate audit is retained separately in
`results/evidence-audit-20261014-current/`. Its raw input specifications and
Python/Node responses accompany `receipt.json`, exact AUC/stratum comparisons,
and an output inventory. The full workflow includes input integrity, exact
semantic/diagnostic coverage, baseline calculations, native specification setup,
both runtime paths, serialization, and archive comparison. Parent Python CPU and
full wall time are reported; child Node CPU was not measured. No speedup is claimed.

The repaired semantic gate rejects duplicate-for-missing contexts, wrong domain
sizes, untyped truth flags, and inconsistent identities. Digests establish byte
identity/consistency, not that an execution happened. Both AUC paths reject an
unpaired, nonbinary, nonfinite, or single-class contrast. The same-information
pooled average-rank baseline agrees on all 296 AUCs; the corrected one-pass
feasible-table comparator agrees with the closed form on all 198 strata.
New tests are admission/oracle controls, not additional research observations.

Actual fresh native execution covers 24 owned reference programs, 72 existing
effective mutants, and 72 carrier-only no-ops on the unchanged finite domains.
All agree with the corresponding retained evidence and six mutants still pass
nominal tests. The other 432 semantic checks, 76,032 state rows, project-transfer
interventions, and original null campaigns were **not regenerated** by this audit.
No upstream code, model, checkpoint, downloaded test, target, or removal campaign
was executed. The full historical generator/rechecker and Linux CI remain
separate workflows; this candidate audit is not installation or scientific acceptance.

The current audit implementation and manuscript amendments used generative-AI
assistance beyond copy-editing. See `AI_ASSISTANCE_NOTICE.md`; human-author review
and applicable ACM-policy eligibility remain outstanding. Historical policy and
author-metadata records are historical, not the authority for the currently
confirmed five-author manuscript.
