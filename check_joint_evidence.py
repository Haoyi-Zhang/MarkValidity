"""Read retained rows; diagnose joint evidence without running transformations.

No carrier, attack, source-extraction, or upstream model routine is imported.
Output is a separate analysis instance; the historical result tree is read-only.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
from covewm.joint_bounds import joint_bounds

SCHEMES = ("lexical", "structural", "hybrid")
ATTACKS = ("format", "rename", "normalize", "random_flip", "strip", "mixed")
TASK_SIZES = dict(zip(
    ("leap_year", "collatz_steps", "raindrops", "grains", "hamming", "isogram",
     "triangle", "luhn", "darts", "armstrong", "nucleotide_count", "reverse_text"),
    (801, 500, 500, 64, 4369, 1365, 1331, 11000, 625, 10000, 1365, 1093),
))
LANGUAGES = ("python", "javascript")
SEVERITIES = tuple(f"{i / 10:.1f}" for i in range(11))
MIXTURES = {
    "balanced": dict.fromkeys(ATTACKS[1:], Fraction(1, 5)),
    "rename-heavy": {"rename": Fraction(54, 100), "random_flip": Fraction(24, 100), "strip": Fraction(22, 100)},
    "structure-heavy": {"normalize": Fraction(54, 100), "random_flip": Fraction(24, 100), "strip": Fraction(22, 100)},
}


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def boolean(value):
    if value in ("True", "true", "1"):
        return True
    if value in ("False", "false", "0"):
        return False
    raise ValueError(f"invalid serialized boolean: {value!r}")


def key(row):
    return (row["scheme"], row["attack"], row["severity"], row["task"],
            row["language"], int(row["payload_index"]))


def indexed(rows, key_function, expected):
    result = {}
    for row in rows:
        k = key_function(row)
        if k in result:
            raise ValueError(f"duplicate evidence key: {k}")
        result[k] = row
    if set(result) != expected:
        raise ValueError(f"evidence coverage mismatch: missing={len(expected-set(result))}, extra={len(set(result)-expected)}")
    return result


def feasible_table_comparator(observations, valid_total=None):
    """Separately enumerate feasible joint counts from the same observations.

    Unlike the closed-form implementation, try every possible x and retain it
    iff a nonempty interval of y values satisfies the marginal. O(u1+1).
    This is implementation independence, not independent authorship/review.
    """
    known = sum(v is True for _, v in observations)
    unknown = sum(v is None for _, v in observations)
    a = sum(decision and v is True for decision, v in observations)
    u1 = sum(decision and v is None for decision, v in observations)
    u0 = sum(not decision and v is None for decision, v in observations)
    lower, upper = (known, known + unknown) if valid_total is None else valid_total
    possible = []
    for x in range(u1 + 1):
        y_lo = max(0, lower - known - x)
        y_hi = min(u0, upper - known - x)
        if y_lo <= y_hi:
            possible.append(a + x)
    if not possible:
        raise ValueError("no feasible table")
    return min(possible), max(possible)


def validate_and_link(robustness, audits):
    expected = set(itertools.product(SCHEMES, ATTACKS, SEVERITIES,
                                     TASK_SIZES, LANGUAGES, range(16)))
    dense = indexed(robustness, key, expected)
    audit_expected = set(itertools.product(TASK_SIZES, LANGUAGES, SCHEMES,
                                          ("carrier_only",) + ATTACKS))
    audit_index = indexed(audits, lambda r: (r["task"], r["language"], r["scheme"], r["condition"]), audit_expected)
    labels = {}
    for (task, language, scheme, condition), row in audit_index.items():
        if int(row["domain_cases"]) != TASK_SIZES[task]:
            raise ValueError("semantic domain mismatch")
        digest = row["source_sha256"]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid source identity")
        parse_ok = boolean(row["parse_ok"])
        equivalent = boolean(row["bounded_equivalent"])
        valid = parse_ok and equivalent
        if condition != "carrier_only":
            # Static producer mapping: audit conditions are severity=1.0,
            # payload=0. This is a declared configuration link, not a newly
            # measured dense source identity or a render/extract observation.
            labels[(scheme, condition, "1.0", task, language, 0)] = valid
    for row in dense.values():
        n, m = int(row["surviving_sites"]), int(row["match_count"])
        if not 0 <= m <= n <= 24:
            raise ValueError("invalid detector counts")
        if int(row["deletions"]) != 24 - n or int(row["realized_bit_changes"]) != n - m:
            raise ValueError("inconsistent operation accounting")
        probability = Fraction(sum(math.comb(n, i) for i in range(m, n + 1)), 2**n)
        if boolean(row["detected"]) != (probability <= Fraction(1, 10000)):
            raise ValueError("detector decision mismatch")
        if not math.isclose(float(row["p_value"]), float(probability), rel_tol=0, abs_tol=1e-15):
            raise ValueError("detector tail mismatch")
    return dense, labels


def ratio(value):
    return str(value) if isinstance(value, Fraction) else str(Fraction(value))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run():
    results = HERE / "results/current/results"
    # Check the retained manifest, without changing its verification status.
    manifest = indexed(read_csv(results / "results_manifest.csv"),
                       lambda r: r["relative_path"],
                       {r["relative_path"] for r in read_csv(results / "results_manifest.csv")})
    consumed = {}
    for name in ("raw/robustness.csv", "raw/semantic_audit.csv", "raw/mutants.csv", "raw/cross_language_parity.csv"):
        data = (results / name).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if manifest[name]["sha256"] != digest or int(manifest[name]["bytes"]) != len(data):
            raise ValueError(f"retained input integrity failure: {name}")
        consumed[name] = digest
    dense, labels = validate_and_link(read_csv(results / "raw/robustness.csv"),
                                     read_csv(results / "raw/semantic_audit.csv"))
    mutants = read_csv(results / "raw/mutants.csv")
    indexed(mutants, lambda r: (r["task"], r["language"], int(r["mutant_id"])),
            set(itertools.product(TASK_SIZES, LANGUAGES, range(1, 4))))
    parity = indexed(read_csv(results / "raw/cross_language_parity.csv"),
                     lambda r: r["task"], set(TASK_SIZES))
    if any(int(r["domain_cases"]) != TASK_SIZES[t] or not boolean(r["equal"])
           or r["python_hash"] != r["javascript_hash"] for t, r in parity.items()):
        raise ValueError("reference parity failure")
    strata = defaultdict(list)
    for k, row in dense.items():
        strata[k[:3]].append((boolean(row["detected"]), labels.get(k)))
    stratum_rows, intervals = [], {}
    for k, observations in sorted(strata.items()):
        bounds = joint_bounds(observations)
        independent = feasible_table_comparator(observations)
        if (bounds.joint_lower, bounds.joint_upper) != independent:
            raise ValueError("same-information comparator disagreement")
        lo, hi = Fraction(bounds.joint_lower, bounds.trials), Fraction(bounds.joint_upper, bounds.trials)
        intervals[k] = lo, hi
        stratum_rows.append(dict(scheme=k[0], attack=k[1], severity=k[2], trials=bounds.trials,
                                 model_detected=bounds.decision_positive,
                                 semantic_labels=bounds.trials-bounds.unknown_positive-bounds.unknown_negative,
                                 joint_lower_count=bounds.joint_lower, joint_upper_count=bounds.joint_upper,
                                 joint_lower_exact=ratio(lo), joint_upper_exact=ratio(hi),
                                 comparator_lower_count=independent[0], comparator_upper_count=independent[1]))
    mixture_rows = []
    for mixture, weights in MIXTURES.items():
        values = {}
        for scheme in SCHEMES:
            lo = sum(weights[a] * sum(intervals[(scheme, a, v)][0] for v in SEVERITIES) / 11 for a in weights)
            hi = sum(weights[a] * sum(intervals[(scheme, a, v)][1] for v in SEVERITIES) / 11 for a in weights)
            values[scheme] = lo, hi
        for scheme, (lo, hi) in values.items():
            strict = all(lo > values[other][1] for other in SCHEMES if other != scheme)
            mixture_rows.append(dict(mixture=mixture, scheme=scheme, joint_lower_exact=ratio(lo),
                                     joint_upper_exact=ratio(hi), joint_lower=f"{float(lo):.12f}",
                                     joint_upper=f"{float(hi):.12f}", certified_strict_winner=strict))
    summary = {
        "analysis": "finite joint-label identification under declared audit-to-state key mapping",
        "dense_state_rows": len(dense), "response_strata": len(strata),
        "semantic_audit_rows": 504, "semantic_labels_linked_to_dense": len(labels),
        "semantic_coverage_fraction": ratio(Fraction(len(labels), len(dense))),
        "unobserved_dense_semantic_labels": len(dense) - len(labels),
        "matched_semantic_passes": sum(labels.values()),
        "model_decision_positive_linked_semantic_passes": sum(boolean(dense[k]["detected"]) and v for k, v in labels.items()),
        "dense_source_extraction_trials_recorded": 0,
        "source_valid_detection_rate_identified_interval": [0, 1],
        "mutants": len(mutants),
        "effective_mutants": sum(boolean(r["parse_ok"]) and not boolean(r["full_domain_equal"]) for r in mutants),
        "nominal_survivors": sum(boolean(r["nominal_equal"]) for r in mutants),
        "cases_per_language": sum(TASK_SIZES.values()),
        "comparator": {"type": "independent feasible-table enumeration, same data and marginals",
                       "strata_equal": len(stratum_rows), "strata_different": 0,
                       "performance_gain_claimed": False},
        "mixtures": mixture_rows,
        "limitations": ["Unknown labels are not experimental failures or successes.",
                        "Sharpness is over unrestricted missing-label completions, not executable programs.",
                        "The key mapping is conditional on the reviewed producer; dense rows lack source hashes.",
                        "No upstream reproduction, external defect, or real extraction-based detection result is supplied."],
        "input_sha256": consumed,
        "environment": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                        "dependencies": "standard library only; -B -S"},
    }
    output = HERE / "results/joint_diagnostic"
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "stratum_bounds.csv", stratum_rows)
    write_csv(output / "mixture_bounds.csv", mixture_rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    run()
