#!/usr/bin/env python3
"""Independent deterministic recheck of generated Cove-WM evidence.

This script does not regenerate measurements. It verifies file hashes, row counts,
key uniqueness, cross-file consistency, formal witnesses, and the central numerical
claims from the frozen result files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

from recheck_extended import recheck_extended

EXPECTED = {
    "task_families": 12,
    "languages": 2,
    "domain_cases_per_language": 33013,
    "cross_language_parity_failures": 0,
    "mutants": 72,
    "ineffective_mutants": 0,
    "nominal_surviving_mutants": 6,
    "semantic_audit_pairs": 504,
    "semantic_audit_failures": 0,
    "metric_intervention_observations": 1296,
    "robustness_observations": 76032,
    "robustness_shard_rows": [38016, 38016],
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_bool(value: str) -> bool:
    if value in {"True", "true", "1"}:
        return True
    if value in {"False", "false", "0"}:
        return False
    raise ValueError(f"not a serialized boolean: {value!r}")


def binomial_tail(n: int, k: int) -> float:
    return sum(math.comb(n, i) for i in range(k, n + 1)) / (2**n)


def external_z_key(matches: int, surviving: int) -> Decimal:
    if surviving <= 0:
        raise ValueError("z score requires a surviving site")
    with localcontext() as context:
        context.prec = 60
        value = Decimal(2 * matches - surviving) / Decimal(surviving).sqrt()
        return value.quantize(Decimal("1e-40"))


def reconstruct_external_protocols(rows: list[dict[str, str]]) -> dict[str, dict[str, Fraction]]:
    by_scheme: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_scheme[row["scheme"]].append(row)
    scores: dict[str, dict[str, Fraction]] = defaultdict(dict)
    for scheme, scheme_rows in by_scheme.items():
        total = len(scheme_rows)
        scores["native_exact_tail_detection"][scheme] = Fraction(
            sum(int(row["detected"]) for row in scheme_rows), total
        )
        scores["srcmarker_bit_accuracy"][scheme] = Fraction(
            sum(int(row["match_count"]) for row in scheme_rows), total * 24
        )
        scores["srcmarker_exact_message"][scheme] = Fraction(
            sum(
                int(row["match_count"]) == 24 and int(row["surviving_sites"]) == 24
                for row in scheme_rows
            ),
            total,
        )
        scores["codeip_available_prefix_exact"][scheme] = Fraction(
            sum(
                int(row["match_count"]) == int(row["surviving_sites"])
                for row in scheme_rows
            ),
            total,
        )

        valid = [row for row in scheme_rows if int(row["surviving_sites"]) > 0]
        valid_total = len(valid)
        surviving_counts = Counter(int(row["surviving_sites"]) for row in valid)
        null_mass: dict[Decimal, Fraction] = defaultdict(Fraction)
        for surviving, frequency in surviving_counts.items():
            denominator = valid_total * (2 ** surviving)
            for matches in range(surviving + 1):
                null_mass[external_z_key(matches, surviving)] += Fraction(
                    frequency * math.comb(surviving, matches), denominator
                )
        positive = Counter(
            external_z_key(int(row["match_count"]), int(row["surviving_sites"]))
            for row in valid
        )
        values = sorted(set(null_mass) | set(positive))
        below: dict[Decimal, Fraction] = {}
        cumulative = Fraction(0)
        for value in values:
            below[value] = cumulative
            cumulative += null_mass.get(value, Fraction(0))
        scores["sweet_exact_null_auroc"][scheme] = sum(
            Fraction(count, valid_total)
            * (below[value] + null_mass.get(value, Fraction(0)) / 2)
            for value, count in positive.items()
        )
        fpr = tpr = Fraction(0)
        best = {Fraction(1, 100): Fraction(0), Fraction(5, 100): Fraction(0)}
        for value in sorted(values, reverse=True):
            fpr += null_mass.get(value, Fraction(0))
            tpr += Fraction(positive.get(value, 0), valid_total)
            for bound in best:
                if fpr <= bound and tpr > best[bound]:
                    best[bound] = tpr
        scores["sweet_tpr_at_fpr_0_01"][scheme] = best[Fraction(1, 100)]
        scores["sweet_tpr_at_fpr_0_05"][scheme] = best[Fraction(5, 100)]
    return scores


def format_fraction(value: Fraction, places: int = 12) -> str:
    """Format an exact rational with deterministic half-even decimal rounding."""
    quantum = Decimal(1).scaleb(-places)
    with localcontext() as context:
        context.prec = 80
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        rounded = decimal_value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    return format(rounded, f".{places}f")


def digest_manifest_rows(rows: list[dict[str, str]]) -> str:
    payload = "\n".join(
        f"{row['relative_path']} {row['sha256']}"
        for row in sorted(rows, key=lambda item: item["relative_path"])
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def require(condition: bool, label: str, findings: list[dict[str, Any]], detail: Any = "") -> None:
    findings.append({"check": label, "pass": bool(condition), "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: {detail}")


def recheck(results: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    summary_path = results / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    for key, expected in EXPECTED.items():
        require(summary[key] == expected, f"summary::{key}", findings, {"expected": expected, "actual": summary[key]})

    parity = read_csv(results / "raw/cross_language_parity.csv")
    require(len(parity) == 12, "parity::row_count", findings, len(parity))
    require(all(as_bool(row["equal"]) for row in parity), "parity::all_equal", findings)
    require(sum(int(row["domain_cases"]) for row in parity) == 33013, "parity::domain_total", findings)

    mutants = read_csv(results / "raw/mutants.csv")
    mutant_keys = [(r["task"], r["language"], r["mutant_id"]) for r in mutants]
    require(len(mutants) == 72, "mutants::row_count", findings, len(mutants))
    require(len(mutant_keys) == len(set(mutant_keys)), "mutants::unique_keys", findings)
    require(all(as_bool(r["parse_ok"]) for r in mutants), "mutants::all_parse", findings)
    require(sum(as_bool(r["full_domain_equal"]) for r in mutants) == 0, "mutants::all_effective", findings)
    require(sum(as_bool(r["nominal_equal"]) for r in mutants) == 6, "mutants::nominal_survivors", findings)

    audits = read_csv(results / "raw/semantic_audit.csv")
    audit_keys = [(r["task"], r["language"], r["scheme"], r["condition"]) for r in audits]
    require(len(audits) == 504, "semantic_audit::row_count", findings, len(audits))
    require(len(audit_keys) == len(set(audit_keys)), "semantic_audit::unique_keys", findings)
    require(all(as_bool(r["parse_ok"]) and as_bool(r["bounded_equivalent"]) for r in audits), "semantic_audit::all_pass", findings)

    interventions = read_csv(results / "raw/metric_interventions.csv")
    intervention_keys = [(r["scheme"], r["task"], r["language"], r["profile_id"]) for r in interventions]
    require(len(interventions) == 1296, "interventions::row_count", findings, len(interventions))
    require(len(intervention_keys) == len(set(intervention_keys)), "interventions::unique_keys", findings)

    robustness = read_csv(results / "raw/robustness.csv")
    shard0 = read_csv(results / "raw/robustness_shard_0.csv")
    shard1 = read_csv(results / "raw/robustness_shard_1.csv")
    key_fields = ("scheme", "attack", "severity", "task", "language", "payload_index")
    keys = [tuple(r[k] for k in key_fields) for r in robustness]
    keys0 = {tuple(r[k] for k in key_fields) for r in shard0}
    keys1 = {tuple(r[k] for k in key_fields) for r in shard1}
    require(len(robustness) == 76032, "robustness::row_count", findings, len(robustness))
    require(len(shard0) == 38016 and len(shard1) == 38016, "robustness::shard_counts", findings, [len(shard0), len(shard1)])
    require(len(keys) == len(set(keys)), "robustness::unique_keys", findings)
    require(not (keys0 & keys1), "robustness::shards_disjoint", findings)
    require(set(keys) == (keys0 | keys1), "robustness::shards_cover_combined", findings)
    require(Counter(r["payload_index"] for r in shard0) == Counter({str(i): 4752 for i in range(8)}), "robustness::shard0_payload_partition", findings)
    require(Counter(r["payload_index"] for r in shard1) == Counter({str(i): 4752 for i in range(8, 16)}), "robustness::shard1_payload_partition", findings)

    external_scores = reconstruct_external_protocols(robustness)
    external_rows = read_csv(results / "derived/external_protocol_replay.csv")
    external_rankings = read_csv(results / "derived/external_protocol_rankings.csv")
    external_lookup = {row["scheme"]: row for row in external_rows}
    external_ok = len(external_rows) == 3 and len(external_rankings) == 21
    for protocol, scheme_scores in external_scores.items():
        ranked = sorted(scheme_scores, key=lambda scheme: (-scheme_scores[scheme], scheme))
        winner = ranked[0]
        for rank, scheme in enumerate(ranked, start=1):
            expected = format_fraction(scheme_scores[scheme])
            external_ok &= external_lookup[scheme][protocol] == expected
            matching = [
                row for row in external_rankings
                if row["protocol"] == protocol and row["scheme"] == scheme
            ]
            external_ok &= len(matching) == 1
            if matching:
                external_ok &= matching[0]["score"] == expected
                external_ok &= matching[0]["rank"] == str(rank)
                external_ok &= matching[0]["winner"] == winner
    for scheme in external_lookup:
        scheme_rows = [row for row in robustness if row["scheme"] == scheme]
        total = len(scheme_rows)
        nonempty = Fraction(
            sum(
                int(row["surviving_sites"]) > 0
                and int(row["match_count"]) == int(row["surviving_sites"])
                for row in scheme_rows
            ),
            total,
        )
        zero_sites = Fraction(
            sum(int(row["surviving_sites"]) == 0 for row in scheme_rows), total
        )
        external_ok &= external_lookup[scheme]["codeip_nonempty_prefix_sensitivity"] == format_fraction(nonempty)
        external_ok &= external_lookup[scheme]["codeip_empty_prefix_contribution"] == format_fraction(zero_sites)

    external_summary = json.loads(
        (results / "derived/external_protocol_replay_summary.json").read_text(encoding="utf-8")
    )
    external_ok &= external_summary["stone_stem"]["status"] == "NOT_COMPUTED_COMPONENT_MISMATCH"
    external_ok &= set(external_summary["distinct_numeric_winners"]) == {"hybrid", "lexical", "structural"}
    require(external_ok, "external_protocols::independent_reconstruction", findings)

    # Recompute all stratum rates from raw detection rows and compare with response curves.
    agg: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in robustness:
        key = (row["scheme"], row["attack"], row["severity"])
        agg[key][0] += int(row["detected"])
        agg[key][1] += 1
    curves = read_csv(results / "derived/response_curves.csv")
    curve_lookup = {(r["scheme"], r["attack"], r["severity"]): r for r in curves}
    require(len(curves) == 198, "response_curves::row_count", findings, len(curves))
    for key, (successes, trials) in agg.items():
        row = curve_lookup[key]
        require(int(row["successes"]) == successes and int(row["trials"]) == trials, f"response_curves::counts::{key}", findings)
        require(math.isclose(float(row["detection_rate"]), successes / trials, rel_tol=0, abs_tol=5e-13), f"response_curves::rate::{key}", findings)

    thresholds = read_csv(results / "derived/curve_thresholds.csv")
    require(len(thresholds) == 15, "curve_thresholds::row_count", findings, len(thresholds))
    threshold_lookup = {(r["scheme"], r["attack"]): r for r in thresholds}
    require(threshold_lookup[("lexical", "rename")]["first_below_0_5"] == "0.2", "curve_thresholds::lexical_rename_half", findings)
    require(threshold_lookup[("structural", "rename")]["first_below_0_5"] == "", "curve_thresholds::structural_rename_invariant", findings)
    require(threshold_lookup[("hybrid", "strip")]["first_zero"] == "0.8", "curve_thresholds::hybrid_strip_zero", findings)

    frontier = read_csv(results / "derived/mixture_frontier.csv")
    require(len(frontier) == 101, "mixture_frontier::row_count", findings, len(frontier))
    require(frontier[0]["rename_share_of_target_mass"] == "0.00" and frontier[-1]["rename_share_of_target_mass"] == "1.00", "mixture_frontier::endpoints", findings)

    exact_family_sums: dict[tuple[str, str], Fraction] = defaultdict(lambda: Fraction(0, 1))
    exact_family_counts: Counter[tuple[str, str]] = Counter()
    for row in curves:
        key = (row["scheme"], row["attack"])
        exact_family_sums[key] += Fraction(int(row["successes"]), int(row["trials"]))
        exact_family_counts[key] += 1
    exact_family_means = {
        key: total / exact_family_counts[key]
        for key, total in exact_family_sums.items()
    }
    target_mass = Fraction(54, 100)
    exact_rows_ok = True
    first_mismatch: dict[str, Any] | None = None
    for index, row in enumerate(frontier):
        rename_share = Fraction(index, 100)
        weights = {
            "rename": target_mass * rename_share,
            "normalize": target_mass * (1 - rename_share),
            "random_flip": Fraction(24, 100),
            "strip": Fraction(22, 100),
            "mixed": Fraction(0, 1),
        }
        exact_scores = {
            scheme: sum(
                (weights[attack] * exact_family_means[(scheme, attack)] for attack in weights),
                Fraction(0, 1),
            )
            for scheme in ("lexical", "structural", "hybrid")
        }
        expected = {scheme: format_fraction(value) for scheme, value in exact_scores.items()}
        expected_winner = max(("lexical", "structural", "hybrid"), key=lambda scheme: exact_scores[scheme])
        if (
            row["rename_share_of_target_mass"] != format_fraction(rename_share, places=2)
            or any(row[scheme] != expected[scheme] for scheme in expected)
            or row["winner"] != expected_winner
        ):
            exact_rows_ok = False
            first_mismatch = {"index": index, "actual": row, "expected": {**expected, "winner": expected_winner}}
            break
    require(exact_rows_ok, "mixture_frontier::exact_rational_rows", findings, first_mismatch or "")

    frontier_scores = [{s: float(row[s]) for s in ("lexical", "structural", "hybrid")} for row in frontier]
    crossing_index = next(index for index in range(1, len(frontier)) if (frontier_scores[index - 1]["lexical"] - frontier_scores[index - 1]["structural"]) * (frontier_scores[index]["lexical"] - frontier_scores[index]["structural"]) <= 0)
    geometry_ok = crossing_index in {50, 51} and all(
        row["hybrid"] < max(row["lexical"], row["structural"]) for row in frontier_scores
    )
    require(geometry_ok, "mixture_frontier::crossing_and_envelope", findings, crossing_index)

    mixtures = read_csv(results / "derived/mixture_scores.csv")
    mix = {(r["mixture"], r["scheme"]): float(r["score"]) for r in mixtures}
    rename_winner = max(("lexical", "structural", "hybrid"), key=lambda s: mix[("rename-heavy", s)])
    structure_winner = max(("lexical", "structural", "hybrid"), key=lambda s: mix[("structure-heavy", s)])
    require(rename_winner == "structural", "mixtures::rename_heavy_winner", findings, rename_winner)
    require(structure_winner == "lexical", "mixtures::structure_heavy_winner", findings, structure_winner)
    require(rename_winner != structure_winner, "mixtures::ranking_reversal", findings)

    duplication = read_csv(results / "derived/duplication_sensitivity.csv")
    for row in duplication:
        base = float(row["base_equal_stratum_macro"])
        after = float(row["macro_after_duplication"])
        shift = float(row["micro_shift"])
        require(math.isclose(base, after, rel_tol=0, abs_tol=1e-15), f"duplication::{row['scheme']}::macro_invariant", findings)
        require(shift > 0.08, f"duplication::{row['scheme']}::micro_changes", findings, shift)

    fp = json.loads((results / "derived/false_positive_summary.json").read_text(encoding="utf-8"))
    exact = binomial_tail(24, 22)
    require(fp["minimal_accepted_match_count"] == 22, "false_positive::threshold", findings)
    require(math.isclose(fp["exact_null_false_positive_probability"], exact, rel_tol=0, abs_tol=1e-20), "false_positive::exact_tail", findings, exact)
    require(fp["monte_carlo"]["false_positives"] == 48 and fp["monte_carlo"]["trials"] == 2_000_000, "false_positive::monte_carlo", findings)
    require(fp["parser_path"]["false_positives"] == 1 and fp["parser_path"]["trials"] == 30_000, "false_positive::parser_path", findings)
    require(fp["zero_failure_trial_requirements"]["1e-04"] == 29956, "false_positive::zero_failure_requirement", findings)

    formal = json.loads((results / "derived/formal_witnesses.json").read_text(encoding="utf-8"))
    require(formal["ranking_reversal"]["rename_heavy_winner"] == "structural", "formal::rename_winner", findings)
    require(formal["ranking_reversal"]["structure_heavy_winner"] == "lexical", "formal::structure_winner", findings)
    require(formal["finite_domain_decidability"]["semantic_audit_failures"] == 0, "formal::semantic_audit", findings)

    # Independently reconstruct the expanded cross-project and sensitivity evidence.
    recheck_extended(results, findings, require)

    # Hash check is last; then rewrite the manifest with a verified status.
    manifest_path = results / "results_manifest.csv"
    manifest = read_csv(manifest_path)
    covered = {r["relative_path"] for r in manifest}
    expected_covered = {
        p.relative_to(results).as_posix()
        for p in results.rglob("*")
        if p.is_file() and p.name not in {"results_manifest.csv", "recheck_report.json"}
    }
    require(covered == expected_covered, "manifest::coverage", findings, {"listed": len(covered), "actual": len(expected_covered)})
    for row in manifest:
        path = results / row["relative_path"]
        require(path.stat().st_size == int(row["bytes"]), f"manifest::size::{row['relative_path']}", findings)
        require(sha256_file(path) == row["sha256"], f"manifest::sha256::{row['relative_path']}", findings)
        row["recheck_status"] = "VERIFIED"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(manifest)

    scientific_manifest = [row for row in manifest if row["relative_path"] != "environment.json"]
    report = {
        "status": "VERIFIED",
        "checks": len(findings),
        "failures": 0,
        "results_directory_sha256": digest_manifest_rows(manifest),
        "scientific_results_sha256": digest_manifest_rows(scientific_manifest),
        "volatile_result_paths": ["environment.json"],
        "findings": findings,
    }
    (results / "recheck_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results")
    args = parser.parse_args()
    report = recheck(args.results.resolve())
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "checks",
                    "failures",
                    "results_directory_sha256",
                    "scientific_results_sha256",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
