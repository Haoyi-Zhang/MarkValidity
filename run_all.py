
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from covewm.benchmark import (  # noqa: E402
    ALPHA,
    ATTACKS,
    MIXTURE_WEIGHTS,
    PAYLOAD_BITS,
    PAYLOAD_COUNT,
    SCHEMES,
    SEVERITIES,
    CarrierState,
    attacked_states,
    binomial_tail,
    carrier_only_states,
    channels,
    detector,
    evaluate_python,
    extract_carriers,
    first_mismatch,
    payload_bits,
    profile_states,
    render_carriers,
    render_program,
    sha256_text,
)
from covewm.metrics import (  # noqa: E402
    clopper_pearson,
    minimum_zero_failure_trials,
    roc_auc,
    source_metrics,
    spearman,
    standardized_linear_model,
    zero_failure_upper,
)
from covewm.tasks import TASKS, TASK_BY_NAME, domain_cases, validate_domains  # noqa: E402
from covewm.external_replay import generate_external_protocol_replay  # noqa: E402
from covewm.extended import (  # noqa: E402
    generate_ambiguity_analysis,
    generate_context_sensitivity,
    generate_decision_functional_sensitivity,
    run_transfer_audit,
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        if not rows:
            raise ValueError(f"fieldnames required for empty CSV: {path}")
        fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decimal_fraction(value: float | int | str | Fraction) -> Fraction:
    """Convert a declared decimal quantity to an exact rational value."""
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value))


def format_fraction(value: Fraction, places: int = 12) -> str:
    """Format an exact rational with deterministic half-even decimal rounding."""
    quantum = Decimal(1).scaleb(-places)
    with localcontext() as context:
        context.prec = 80
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        rounded = decimal_value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    return format(rounded, f".{places}f")


def program_sources(task, language: str) -> tuple[str, list[tuple[str, str, str]], list[tuple[str, str, str, str]]]:
    if language == "python":
        reference_template = task.python_reference
        mutants = task.python_mutants
    else:
        reference_template = task.javascript_reference
        mutants = task.javascript_mutants

    reference = render_program(reference_template, language, None)
    mutant_programs = [
        (f"mutant::{task.name}::{language}::{index + 1}", source.rstrip() + "\n", description)
        for index, (source, description) in enumerate(zip(mutants, task.mutant_descriptions))
    ]

    audit_programs: list[tuple[str, str, str, str]] = []
    conditions = ("carrier_only",) + ATTACKS
    for scheme in SCHEMES:
        expected = payload_bits(task.name, language, 0)
        for condition in conditions:
            if condition == "carrier_only":
                states = carrier_only_states(expected, scheme)
                formatted = False
            else:
                states, _ = attacked_states(
                    expected, scheme, condition, 1.0, task.name, language, 0
                )
                formatted = condition == "format"
            source = render_program(reference_template, language, states, formatted=formatted)
            program_id = f"audit::{task.name}::{language}::{scheme}::{condition}"
            audit_programs.append((program_id, source, scheme, condition))
    return reference, mutant_programs, audit_programs


def evaluate_python_programs(
    task,
    reference_source: str,
    mutant_programs: list[tuple[str, str, str]],
    audit_programs: list[tuple[str, str, str, str]],
) -> tuple[dict[str, dict[str, Any]], str]:
    cases = domain_cases(task.name)
    nominal = [list(case) for case in task.nominal_cases]
    reference_outputs, reference_hash = evaluate_python(reference_source, cases)
    reference_nominal, reference_nominal_hash = evaluate_python(reference_source, nominal)
    results: dict[str, dict[str, Any]] = {
        f"reference::{task.name}::python": {
            "id": f"reference::{task.name}::python",
            "role": "reference",
            "parse_ok": True,
            "domain_hash": reference_hash,
            "nominal_hash": reference_nominal_hash,
            "domain_equal": True,
            "nominal_equal": True,
            "first_mismatch_index": None,
            "error": "",
        }
    }
    for program_id, source, _description in mutant_programs:
        try:
            outputs, digest = evaluate_python(source, cases)
            nominal_outputs, nominal_digest = evaluate_python(source, nominal)
            mismatch = first_mismatch(reference_outputs, outputs)
            nominal_mismatch = first_mismatch(reference_nominal, nominal_outputs)
            results[program_id] = {
                "id": program_id,
                "role": "mutant",
                "parse_ok": True,
                "domain_hash": digest,
                "nominal_hash": nominal_digest,
                "domain_equal": mismatch is None,
                "nominal_equal": nominal_mismatch is None,
                "first_mismatch_index": mismatch,
                "error": "",
            }
        except Exception as exc:
            results[program_id] = {
                "id": program_id,
                "role": "mutant",
                "parse_ok": False,
                "domain_hash": "",
                "nominal_hash": "",
                "domain_equal": False,
                "nominal_equal": False,
                "first_mismatch_index": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
    for program_id, source, _scheme, _condition in audit_programs:
        try:
            outputs, digest = evaluate_python(source, cases)
            nominal_outputs, nominal_digest = evaluate_python(source, nominal)
            mismatch = first_mismatch(reference_outputs, outputs)
            nominal_mismatch = first_mismatch(reference_nominal, nominal_outputs)
            results[program_id] = {
                "id": program_id,
                "role": "audit",
                "parse_ok": True,
                "domain_hash": digest,
                "nominal_hash": nominal_digest,
                "domain_equal": mismatch is None,
                "nominal_equal": nominal_mismatch is None,
                "first_mismatch_index": mismatch,
                "error": "",
            }
        except Exception as exc:
            results[program_id] = {
                "id": program_id,
                "role": "audit",
                "parse_ok": False,
                "domain_hash": "",
                "nominal_hash": "",
                "domain_equal": False,
                "nominal_equal": False,
                "first_mismatch_index": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
    return results, reference_hash


def apply_format_fraction(source: str, language: str, fraction: float, profile_id: str) -> str:
    if fraction <= 0:
        return source
    lines = source.splitlines()
    marker_positions = [i for i, line in enumerate(lines) if "WM_SITE" in line]
    count = round(len(marker_positions) * fraction)
    selected = set(marker_positions[:count])
    output: list[str] = []
    for position, line in enumerate(lines):
        if position in selected:
            if language == "python":
                output.append("    # metric-format intervention")
            else:
                output.append("  // metric-format intervention")
            output.append("")
        output.append(line)
    return "\n".join(output).rstrip() + "\n"


def metric_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = [
        {"profile_id": "baseline", "format_fraction": 0.0, "lexical_fraction": 0.0, "structural_fraction": 0.0, "deletion_fraction": 0.0},
        {"profile_id": "format_025", "format_fraction": 0.25, "lexical_fraction": 0.0, "structural_fraction": 0.0, "deletion_fraction": 0.0},
        {"profile_id": "format_050", "format_fraction": 0.50, "lexical_fraction": 0.0, "structural_fraction": 0.0, "deletion_fraction": 0.0},
        {"profile_id": "format_100", "format_fraction": 1.00, "lexical_fraction": 0.0, "structural_fraction": 0.0, "deletion_fraction": 0.0},
    ]
    for fraction in (0.25, 0.50, 0.75, 1.00):
        profiles.append({"profile_id": f"lexical_{fraction:.2f}".replace(".", ""), "format_fraction": 0.0, "lexical_fraction": fraction, "structural_fraction": 0.0, "deletion_fraction": 0.0})
    for fraction in (0.25, 0.50, 0.75, 1.00):
        profiles.append({"profile_id": f"structural_{fraction:.2f}".replace(".", ""), "format_fraction": 0.0, "lexical_fraction": 0.0, "structural_fraction": fraction, "deletion_fraction": 0.0})
    for fraction in (0.25, 0.50, 0.75, 1.00):
        profiles.append({"profile_id": f"deletion_{fraction:.2f}".replace(".", ""), "format_fraction": 0.0, "lexical_fraction": 0.0, "structural_fraction": 0.0, "deletion_fraction": fraction})
    profiles.extend(
        [
            {"profile_id": "mixed_low", "format_fraction": 0.25, "lexical_fraction": 0.25, "structural_fraction": 0.25, "deletion_fraction": 0.25},
            {"profile_id": "mixed_high", "format_fraction": 0.50, "lexical_fraction": 0.50, "structural_fraction": 0.50, "deletion_fraction": 0.50},
        ]
    )
    assert len(profiles) == 18
    return profiles


def validate_semantic_evidence(parity_rows, mutant_rows, audit_rows) -> None:
    """Stop before interpreting an invalid semantic contrast.

    Raw observation tables are written first, so rejected runs retain their
    counterevidence. This gate is not a test of natural defect prevalence.
    """
    failures = []
    if len(parity_rows) != len(TASKS) or not all(row["equal"] for row in parity_rows):
        failures.append("cross-language reference parity")
    if len(mutant_rows) != len(TASKS) * 2 * 3 or not all(
        row["parse_ok"] and not row["full_domain_equal"] for row in mutant_rows
    ):
        failures.append("mutant parsing/effectiveness")
    if len(audit_rows) != len(TASKS) * 2 * len(SCHEMES) * (1 + len(ATTACKS)) or not all(
        row["parse_ok"] and row["bounded_equivalent"] for row in audit_rows
    ):
        failures.append("no-op parsing/bounded equivalence")
    if failures:
        raise ValueError("semantic evidence gate failed: " + "; ".join(failures))


def run(output: Path) -> dict[str, Any]:
    validate_domains()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    programs_root = output / "programs"
    task_cards_root = output / "task_cards"
    source_map: dict[str, tuple[str, str, str]] = {}
    python_results: dict[str, dict[str, Any]] = {}
    python_reference_hashes: dict[str, str] = {}
    node_spec = {"tasks": {}}

    # Generate programs, task cards, and execute Python.
    for task in TASKS:
        cases = domain_cases(task.name)
        card = {
            "task": task.name,
            "domain_size": len(cases),
            "nominal_case_count": len(task.nominal_cases),
            "nominal_cases": [list(case) for case in task.nominal_cases],
            "python_signature": task.python_reference.splitlines()[0],
            "javascript_signature": task.javascript_reference.splitlines()[0],
            "mutations": list(task.mutant_descriptions),
            "observation_normalization": "Canonical JSON with sorted object keys; explicit exception records.",
            "timeout_policy": "Deterministic tasks include an internal Collatz guard; any runtime failure is retained as evidence.",
            "construct_note": task.construct_note,
        }
        write_json(task_cards_root / f"{task.name}.json", card)

        for language in ("python", "javascript"):
            reference, mutants, audits = program_sources(task, language)
            extension = "py" if language == "python" else "js"
            task_dir = programs_root / language / task.name
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / f"reference.{extension}").write_text(reference, encoding="utf-8")
            source_map[f"reference::{task.name}::{language}"] = (reference, language, "reference")
            for index, (program_id, source, description) in enumerate(mutants, start=1):
                (task_dir / f"mutant_{index}.{extension}").write_text(source, encoding="utf-8")
                source_map[program_id] = (source, language, description)
            for program_id, source, scheme, condition in audits:
                source_map[program_id] = (source, language, f"{scheme}/{condition}")

            if language == "python":
                task_results, reference_hash = evaluate_python_programs(task, reference, mutants, audits)
                python_results.update(task_results)
                python_reference_hashes[task.name] = reference_hash
            else:
                node_programs = [
                    {"id": f"reference::{task.name}::javascript", "role": "reference", "source": reference}
                ]
                node_programs.extend(
                    {"id": program_id, "role": "mutant", "source": source}
                    for program_id, source, _description in mutants
                )
                node_programs.extend(
                    {"id": program_id, "role": "audit", "source": source}
                    for program_id, source, _scheme, _condition in audits
                )
                node_spec["tasks"][task.name] = {
                    "cases": cases,
                    "nominal_cases": [list(case) for case in task.nominal_cases],
                    "programs": node_programs,
                }

    with tempfile.TemporaryDirectory(prefix="covewm-node-") as temp_dir:
        spec_path = Path(temp_dir) / "spec.json"
        spec_path.write_text(json.dumps(node_spec, separators=(",", ":")), encoding="utf-8")
        completed = subprocess.run(
            ["node", str(HERE / "js" / "batch_runner.js"), str(spec_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )
        node_results = json.loads(completed.stdout)

    javascript_results: dict[str, dict[str, Any]] = {}
    javascript_reference_hashes: dict[str, str] = {}
    for task_name, task_result in node_results["tasks"].items():
        for program in task_result["programs"]:
            javascript_results[program["id"]] = program
            if program["role"] == "reference":
                javascript_reference_hashes[task_name] = program["domain_hash"]

    parity_rows: list[dict[str, Any]] = []
    for task in TASKS:
        parity_rows.append(
            {
                "task": task.name,
                "domain_cases": task.domain_size,
                "python_hash": python_reference_hashes[task.name],
                "javascript_hash": javascript_reference_hashes[task.name],
                "equal": python_reference_hashes[task.name] == javascript_reference_hashes[task.name],
            }
        )
    write_csv(output / "raw" / "cross_language_parity.csv", parity_rows)

    # Mutant evidence and semantic audits.
    mutant_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    metric_names = [
        "character_similarity",
        "token_similarity",
        "identifier_normalized_similarity",
        "ast_type_similarity",
        "control_profile_similarity",
        "identifier_multiset_similarity",
        "identifier_style_similarity",
    ]

    for task in TASKS:
        for language in ("python", "javascript"):
            results = python_results if language == "python" else javascript_results
            reference_id = f"reference::{task.name}::{language}"
            reference_source = source_map[reference_id][0]
            for index, description in enumerate(task.mutant_descriptions, start=1):
                program_id = f"mutant::{task.name}::{language}::{index}"
                result = results[program_id]
                source = source_map[program_id][0]
                row = {
                    "task": task.name,
                    "language": language,
                    "mutant_id": index,
                    "description": description,
                    "source_sha256": sha256_text(source),
                    "parse_ok": result["parse_ok"],
                    "full_domain_equal": result["domain_equal"],
                    "nominal_equal": result["nominal_equal"],
                    "first_mismatch_index": result["first_mismatch_index"],
                    "domain_cases": task.domain_size,
                }
                mutant_rows.append(row)
                metrics = source_metrics(reference_source, source, language)
                diagnostic_rows.append(
                    {
                        "pair_id": program_id,
                        "task": task.name,
                        "language": language,
                        "pair_class": "mutant",
                        "bounded_equivalent": int(result["parse_ok"] and result["domain_equal"]),
                        "nominal_test_pass": int(result["nominal_equal"]),
                        **metrics,
                    }
                )

            for scheme in SCHEMES:
                for condition in ("carrier_only",) + ATTACKS:
                    program_id = f"audit::{task.name}::{language}::{scheme}::{condition}"
                    result = results[program_id]
                    source = source_map[program_id][0]
                    metrics = source_metrics(reference_source, source, language)
                    audit_rows.append(
                        {
                            "task": task.name,
                            "language": language,
                            "scheme": scheme,
                            "condition": condition,
                            "source_sha256": sha256_text(source),
                            "parse_ok": result["parse_ok"],
                            "bounded_equivalent": result["domain_equal"],
                            "nominal_equal": result["nominal_equal"],
                            "domain_cases": task.domain_size,
                            "first_mismatch_index": result["first_mismatch_index"],
                            **metrics,
                        }
                    )
                    diagnostic_rows.append(
                        {
                            "pair_id": program_id,
                            "task": task.name,
                            "language": language,
                            "pair_class": "no_op_transformation",
                            "bounded_equivalent": int(result["parse_ok"] and result["domain_equal"]),
                            "nominal_test_pass": int(result["nominal_equal"]),
                            **metrics,
                        }
                    )

    write_csv(output / "raw" / "mutants.csv", mutant_rows)
    write_csv(output / "raw" / "semantic_audit.csv", audit_rows)
    write_csv(output / "raw" / "diagnostic_pairs.csv", diagnostic_rows)
    validate_semantic_evidence(parity_rows, mutant_rows, audit_rows)

    labels = [int(row["bounded_equivalent"]) for row in diagnostic_rows]
    auc_rows = [
        {
            "indicator": "nominal_test_pass_rate",
            "roc_auc": roc_auc(labels, [float(row["nominal_test_pass"]) for row in diagnostic_rows]),
        }
    ]
    for metric in metric_names:
        auc_rows.append(
            {
                "indicator": metric,
                "roc_auc": roc_auc(labels, [float(row[metric]) for row in diagnostic_rows]),
            }
        )
    write_csv(output / "derived" / "semantic_proxy_auc.csv", auc_rows)

    # Dense robustness matrix: two disjoint payload shards plus a combined file.
    robustness_rows: list[dict[str, Any]] = []
    shard_rows = {0: [], 1: []}
    stratum_counts: dict[tuple[str, str, float], list[int]] = defaultdict(lambda: [0, 0])
    for scheme in SCHEMES:
        for attack in ATTACKS:
            for severity in SEVERITIES:
                for task in TASKS:
                    for language in ("python", "javascript"):
                        for payload_index in range(PAYLOAD_COUNT):
                            expected = payload_bits(task.name, language, payload_index)
                            states, metadata = attacked_states(
                                expected,
                                scheme,
                                attack,
                                severity,
                                task.name,
                                language,
                                payload_index,
                            )
                            result = detector(states)
                            row = {
                                "scheme": scheme,
                                "attack": attack,
                                "severity": f"{severity:.1f}",
                                "task": task.name,
                                "language": language,
                                "payload_index": payload_index,
                                "key_id": metadata["key_id"],
                                "effective_severity": f"{metadata['effective_severity']:.6f}",
                                "requested_operations": f"{metadata['eligible_sites'] * metadata['effective_severity']:.6f}",
                                "realized_bit_changes": result["realized_bit_changes"],
                                "deletions": result["deletions"],
                                "surviving_sites": result["surviving_sites"],
                                "match_count": result["match_count"],
                                "match_rate": f"{result['match_rate']:.12f}",
                                "p_value": f"{result['p_value']:.18g}",
                                "detected": result["detected"],
                            }
                            robustness_rows.append(row)
                            shard_rows[0 if payload_index < 8 else 1].append(row)
                            key = (scheme, attack, severity)
                            stratum_counts[key][0] += result["detected"]
                            stratum_counts[key][1] += 1

    robustness_fields = list(robustness_rows[0])
    write_csv(output / "raw" / "robustness_shard_0.csv", shard_rows[0], robustness_fields)
    write_csv(output / "raw" / "robustness_shard_1.csv", shard_rows[1], robustness_fields)
    write_csv(output / "raw" / "robustness.csv", robustness_rows, robustness_fields)

    external_protocol_summary = generate_external_protocol_replay(
        robustness_rows, output / "derived"
    )

    response_rows: list[dict[str, Any]] = []
    family_means: dict[tuple[str, str], Fraction] = {}
    for scheme in SCHEMES:
        for attack in ATTACKS:
            exact_rates: list[Fraction] = []
            for severity in SEVERITIES:
                successes, trials = stratum_counts[(scheme, attack, severity)]
                lower, upper = clopper_pearson(successes, trials)
                rate = Fraction(successes, trials)
                exact_rates.append(rate)
                response_rows.append(
                    {
                        "scheme": scheme,
                        "attack": attack,
                        "severity": f"{severity:.1f}",
                        "successes": successes,
                        "trials": trials,
                        "detection_rate": format_fraction(rate),
                        "cp95_lower": f"{lower:.12f}",
                        "cp95_upper": f"{upper:.12f}",
                    }
                )
            family_means[(scheme, attack)] = sum(exact_rates, Fraction(0, 1)) / len(exact_rates)
    write_csv(output / "derived" / "response_curves.csv", response_rows)

    family_rows = [
        {"scheme": scheme, "attack": attack, "mean_detection_rate": format_fraction(family_means[(scheme, attack)])}
        for scheme in SCHEMES
        for attack in ATTACKS
    ]
    write_csv(output / "derived" / "attack_family_means.csv", family_rows)

    mixture_rows: list[dict[str, Any]] = []
    for mixture, weights in MIXTURE_WEIGHTS.items():
        exact_weights = {attack: decimal_fraction(weight) for attack, weight in weights.items()}
        scores = []
        for scheme in SCHEMES:
            score = sum(
                (exact_weights[attack] * family_means[(scheme, attack)] for attack in exact_weights),
                Fraction(0, 1),
            )
            scores.append((scheme, score))
        ranked = sorted(scores, key=lambda item: (-item[1], item[0]))
        rank = {scheme: position + 1 for position, (scheme, _score) in enumerate(ranked)}
        for scheme, score in scores:
            mixture_rows.append(
                {
                    "mixture": mixture,
                    "scheme": scheme,
                    "score": format_fraction(score),
                    "rank": rank[scheme],
                }
            )
    write_csv(output / "derived" / "mixture_scores.csv", mixture_rows)

    # Secondary deterministic views used by the article and online supplement.
    threshold_rows: list[dict[str, Any]] = []
    response_lookup = {
        (row["scheme"], row["attack"]): []
        for row in response_rows
    }
    for row in response_rows:
        response_lookup[(row["scheme"], row["attack"])].append(row)
    for scheme in SCHEMES:
        for attack in ("rename", "normalize", "random_flip", "strip", "mixed"):
            ordered = sorted(response_lookup[(scheme, attack)], key=lambda row: float(row["severity"]))

            def first_severity(predicate: Callable[[float], bool]) -> str:
                values = [float(row["severity"]) for row in ordered if predicate(float(row["detection_rate"]))]
                return "" if not values else f"{values[0]:.1f}"

            threshold_rows.append(
                {
                    "scheme": scheme,
                    "attack": attack,
                    "first_below_0_5": first_severity(lambda value: value < 0.5),
                    "first_below_0_1": first_severity(lambda value: value < 0.1),
                    "first_below_0_01": first_severity(lambda value: value < 0.01),
                    "first_zero": first_severity(lambda value: value == 0.0),
                }
            )
    write_csv(output / "derived" / "curve_thresholds.csv", threshold_rows)

    frontier_rows: list[dict[str, Any]] = []
    target_mass = Fraction(54, 100)
    background_weights = {
        "random_flip": Fraction(24, 100),
        "strip": Fraction(22, 100),
        "mixed": Fraction(0, 1),
    }
    for index in range(101):
        rename_share = Fraction(index, 100)
        weights = {
            "rename": target_mass * rename_share,
            "normalize": target_mass * (1 - rename_share),
            **background_weights,
        }
        scores = {
            scheme: sum(
                (weights[attack] * family_means[(scheme, attack)] for attack in weights),
                Fraction(0, 1),
            )
            for scheme in SCHEMES
        }
        frontier_rows.append(
            {
                "rename_share_of_target_mass": format_fraction(rename_share, places=2),
                **{scheme: format_fraction(scores[scheme]) for scheme in SCHEMES},
                "winner": max(SCHEMES, key=lambda scheme: scores[scheme]),
            }
        )
    write_csv(output / "derived" / "mixture_frontier.csv", frontier_rows)

    duplication_rows: list[dict[str, Any]] = []
    nonformat = ("rename", "normalize", "random_flip", "strip", "mixed")
    favorite = {"lexical": "normalize", "structural": "rename", "hybrid": "strip"}
    for scheme in SCHEMES:
        macro = sum(
            (family_means[(scheme, attack)] for attack in nonformat),
            Fraction(0, 1),
        ) / len(nonformat)
        favored_rate = family_means[(scheme, favorite[scheme])]
        # The favored attack-family row is represented 20 times total: 19 added duplicates.
        duplicated_micro = (5 * macro + 19 * favored_rate) / 24
        duplication_rows.append(
            {
                "scheme": scheme,
                "favored_attack": favorite[scheme],
                "base_equal_stratum_macro": format_fraction(macro),
                "duplicated_row_micro": format_fraction(duplicated_micro),
                "micro_shift": format_fraction(duplicated_micro - macro),
                "macro_after_duplication": format_fraction(macro),
                "copies_total": 20,
            }
        )
    write_csv(output / "derived" / "duplication_sensitivity.csv", duplication_rows)

    # Factorized intervention matrix and diagnostic models.
    intervention_rows: list[dict[str, Any]] = []
    profiles = metric_profiles()
    for scheme in SCHEMES:
        for task in TASKS:
            for language in ("python", "javascript"):
                template = task.python_reference if language == "python" else task.javascript_reference
                reference_source = render_program(template, language, None)
                expected = payload_bits(task.name, language, 0)
                for profile in profiles:
                    states = profile_states(
                        expected,
                        scheme,
                        task.name,
                        language,
                        profile["profile_id"],
                        profile["lexical_fraction"],
                        profile["structural_fraction"],
                        profile["deletion_fraction"],
                    )
                    source = render_program(template, language, states)
                    source = apply_format_fraction(
                        source, language, profile["format_fraction"], profile["profile_id"]
                    )
                    metrics = source_metrics(reference_source, source, language)
                    detection = detector(states)
                    row: dict[str, Any] = {
                        "scheme": scheme,
                        "task": task.name,
                        "language": language,
                        **profile,
                        **metrics,
                        "carrier_retention": detection["surviving_sites"] / PAYLOAD_BITS,
                        "payload_match_rate": detection["match_rate"],
                    }
                    for metric in metric_names:
                        row[metric.replace("_similarity", "_distortion")] = 1.0 - float(row[metric])
                    intervention_rows.append(row)
    assert len(intervention_rows) == 1296
    write_csv(output / "raw" / "metric_interventions.csv", intervention_rows)

    predictors = ["format_fraction", "lexical_fraction", "structural_fraction", "deletion_fraction"]
    responses = [metric.replace("_similarity", "_distortion") for metric in metric_names] + [
        "carrier_retention",
        "payload_match_rate",
    ]
    coefficient_rows: list[dict[str, Any]] = []
    for response in responses:
        model = standardized_linear_model(intervention_rows, response, predictors)
        coefficient_rows.append({"response": response, **model})
    write_csv(output / "derived" / "intervention_models.csv", coefficient_rows)

    correlation_rows: list[dict[str, Any]] = []
    distortion_names = [metric.replace("_similarity", "_distortion") for metric in metric_names]
    for left in distortion_names:
        for right in distortion_names:
            correlation_rows.append(
                {
                    "left_metric": left,
                    "right_metric": right,
                    "spearman": f"{spearman([float(row[left]) for row in intervention_rows], [float(row[right]) for row in intervention_rows]):.12f}",
                }
            )
    write_csv(output / "derived" / "metric_rank_correlations.csv", correlation_rows)

    # External-validity and analysis-choice stress tests.  These modules read
    # the frozen rows and never feed results back into tasks, attacks, weights,
    # thresholds, or detector behavior.
    transfer_summary = run_transfer_audit(HERE / "corpus", output)
    context_summary = generate_context_sensitivity(
        diagnostic_rows,
        intervention_rows,
        robustness_rows,
        MIXTURE_WEIGHTS,
        output,
    )
    ambiguity_summary = generate_ambiguity_analysis(
        robustness_rows,
        MIXTURE_WEIGHTS,
        output,
    )
    decision_functional_summary = generate_decision_functional_sensitivity(
        robustness_rows,
        output,
    )

    # Exact detector calibration and deterministic checks.
    threshold = None
    exact_probability = None
    for accepted_matches in range(PAYLOAD_BITS + 1):
        probability = binomial_tail(PAYLOAD_BITS, accepted_matches)
        if probability <= ALPHA:
            threshold = accepted_matches
            exact_probability = probability
            break
    assert threshold == 22

    rng = random.Random(69)
    monte_carlo_trials = 2_000_000
    monte_carlo_false_positives = sum(
        rng.getrandbits(PAYLOAD_BITS).bit_count() >= threshold
        for _ in range(monte_carlo_trials)
    )
    mc_lower, mc_upper = clopper_pearson(monte_carlo_false_positives, monte_carlo_trials)

    parser_rng = random.Random(2)
    parser_trials = 30_000
    parser_false_positives = 0
    for trial in range(parser_trials):
        word = parser_rng.getrandbits(PAYLOAD_BITS)
        observed = [(word >> index) & 1 for index in range(PAYLOAD_BITS)]
        scheme = SCHEMES[trial % len(SCHEMES)]
        language = ("python", "javascript")[trial % 2]
        states = [
            CarrierState(index, channel, 1, bit, True, "null")
            for index, (channel, bit) in enumerate(zip(channels(scheme), observed))
        ]
        source = render_carriers(language, states)
        extracted = extract_carriers(source, language)
        if len(extracted) != PAYLOAD_BITS:
            raise AssertionError(("parser extraction failure", trial, scheme, language))
        parsed_states = [
            CarrierState(index, channels(scheme)[index], 1, extracted[index], True, "parsed_null")
            for index in range(PAYLOAD_BITS)
        ]
        parser_false_positives += detector(parsed_states)["detected"]

    false_positive_summary = {
        "payload_bits": PAYLOAD_BITS,
        "nominal_alpha": ALPHA,
        "minimal_accepted_match_count": threshold,
        "exact_null_false_positive_probability": exact_probability,
        "monte_carlo": {
            "seed": 69,
            "trials": monte_carlo_trials,
            "false_positives": monte_carlo_false_positives,
            "rate": monte_carlo_false_positives / monte_carlo_trials,
            "clopper_pearson_95": [mc_lower, mc_upper],
        },
        "parser_path": {
            "seed": 2,
            "trials": parser_trials,
            "false_positives": parser_false_positives,
            "rate": parser_false_positives / parser_trials,
        },
        "zero_failure_trial_requirements": {
            f"{target:.0e}": minimum_zero_failure_trials(target)
            for target in (1e-2, 1e-3, 1e-4, 1e-5, 1e-6)
        },
        "zero_failure_5000_upper_95": zero_failure_upper(5000),
    }
    write_json(output / "derived" / "false_positive_summary.json", false_positive_summary)

    # Formal witnesses and compact result summary.
    mixture_lookup = {
        (row["mixture"], row["scheme"]): float(row["score"])
        for row in mixture_rows
    }
    formal = {
        "finite_domain_decidability": {
            "preconditions_checked": True,
            "domain_cases_per_language": sum(task.domain_size for task in TASKS),
            "semantic_audit_pairs": len(audit_rows),
            "semantic_audit_failures": sum(
                not (row["parse_ok"] and row["bounded_equivalent"]) for row in audit_rows
            ),
        },
        "ranking_reversal": {
            "rename_heavy_winner": max(SCHEMES, key=lambda scheme: mixture_lookup[("rename-heavy", scheme)]),
            "structure_heavy_winner": max(SCHEMES, key=lambda scheme: mixture_lookup[("structure-heavy", scheme)]),
            "witness": "Winners differ under fixed observations and declared attack mixtures.",
        },
        "duplication_sensitivity": duplication_rows,
        "zero_failure_upper_bound": {
            "formula": "1 - gamma^(1/n)",
            "n_for_1e-4": minimum_zero_failure_trials(1e-4),
            "positive_for_every_finite_n": True,
        },
        "discrete_detector_calibration": {
            "n": PAYLOAD_BITS,
            "k": threshold,
            "exact_probability": exact_probability,
        },
        "analysis_configuration_sensitivity": {
            "holdout_recomputations": context_summary["holdout_recomputations"],
            "bootstrap_replicates": context_summary["bootstrap_replicates"],
            "decision_functional_winners": decision_functional_summary["winners"],
            "mixture_uncertainty_rows": ambiguity_summary["robust_winner_rows"],
        },
        "project_transfer_negative_control": {
            "projects": transfer_summary["projects"],
            "modules": transfer_summary["modules"],
            "summary": transfer_summary["summary"],
        },
    }
    write_json(output / "derived" / "formal_witnesses.json", formal)

    nominal_survivors = sum(row["nominal_equal"] for row in mutant_rows)
    semantic_failures = sum(
        not (row["parse_ok"] and row["bounded_equivalent"]) for row in audit_rows
    )
    summary = {
        "task_families": len(TASKS),
        "languages": 2,
        "domain_cases_per_language": sum(task.domain_size for task in TASKS),
        "cross_language_parity_failures": sum(not row["equal"] for row in parity_rows),
        "mutants": len(mutant_rows),
        "ineffective_mutants": sum(row["full_domain_equal"] for row in mutant_rows),
        "nominal_surviving_mutants": nominal_survivors,
        "semantic_audit_pairs": len(audit_rows),
        "semantic_audit_failures": semantic_failures,
        "metric_intervention_observations": len(intervention_rows),
        "robustness_observations": len(robustness_rows),
        "robustness_shard_rows": [len(shard_rows[0]), len(shard_rows[1])],
        "auc": {row["indicator"]: row["roc_auc"] for row in auc_rows},
        "mixture_scores": mixture_rows,
        "duplication_sensitivity": duplication_rows,
        "false_positive": false_positive_summary,
        "project_transfer": transfer_summary,
        "context_sensitivity": {
            "holdout_recomputations": context_summary["holdout_recomputations"],
            "bootstrap_replicates": context_summary["bootstrap_replicates"],
            "contextual_auc_rows": context_summary["contextual_auc_rows"],
        },
        "mixture_ambiguity": {
            "envelope_rows": ambiguity_summary["envelope_rows"],
            "pairwise_rows": ambiguity_summary["pairwise_rows"],
            "robust_winner_rows": ambiguity_summary["robust_winner_rows"],
        },
        "decision_functional_sensitivity": decision_functional_summary,
        "external_protocol_replay": external_protocol_summary,
    }
    write_json(output / "summary.json", summary)

    environment = {
        "executed_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "node": node_results["node_version"],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "dependencies": "Python standard library and Node.js standard library only.",
        "command": "python run_all.py --out results",
    }
    write_json(output / "environment.json", environment)

    # File-level evidence manifest. Exclude the manifest from its own coverage.
    manifest_rows: list[dict[str, Any]] = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "results_manifest.csv":
            manifest_rows.append(
                {
                    "relative_path": path.relative_to(output).as_posix(),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                    "producer_command": "python run_all.py --out results",
                    "recheck_status": "PENDING_RECHECK",
                }
            )
    write_csv(output / "results_manifest.csv", manifest_rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the complete Cove-WM benchmark.")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args()
    summary = run(args.out.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
