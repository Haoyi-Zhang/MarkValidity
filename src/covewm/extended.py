from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import keyword
import math
import random
import tokenize
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import median
from typing import Any, Callable, Sequence

from .benchmark import ATTACKS, MIXTURE_WEIGHTS, SCHEMES, SEVERITIES
from .metrics import clopper_pearson, roc_auc, spearman, tokens

DESTRUCTIVE_ATTACKS = ("rename", "normalize", "random_flip", "strip", "mixed")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        if not rows:
            raise ValueError(f"fieldnames required for empty CSV: {path}")
        fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _weighted_multiset_jaccard(left: Counter[Any], right: Counter[Any]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 1.0
    numerator = sum(min(left[key], right[key]) for key in keys)
    denominator = sum(max(left[key], right[key]) for key in keys)
    return numerator / denominator if denominator else 1.0


def _character_ngram_similarity(left: str, right: str, width: int = 5) -> float:
    def grams(value: str) -> Counter[str]:
        if len(value) < width:
            return Counter(value)
        return Counter(value[index : index + width] for index in range(len(value) - width + 1))

    return _weighted_multiset_jaccard(grams(left), grams(right))


def _token_multiset_similarity(left: str, right: str) -> float:
    return _weighted_multiset_jaccard(Counter(tokens(left, "python")), Counter(tokens(right, "python")))


def _ast_profile_similarity(left: str, right: str) -> float:
    def profile(value: str) -> Counter[str]:
        try:
            return Counter(type(node).__name__ for node in ast.walk(ast.parse(value)))
        except SyntaxError:
            return Counter({"PARSE_FAILURE": 1})

    return _weighted_multiset_jaccard(profile(left), profile(right))


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty percentile input")
    position = q * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


class _ScopeNameCollector(ast.NodeVisitor):
    def __init__(self, target: ast.AST, name: str) -> None:
        self.target = target
        self.name = name
        self.positions: set[tuple[int, int]] = set()
        self._inside = False

    def visit(self, node: ast.AST) -> Any:
        if node is self.target:
            prior = self._inside
            self._inside = True
            result = super().visit(node)
            self._inside = prior
            return result
        if self._inside and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return None
        return super().visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        if self._inside and node.arg == self.name:
            self.positions.add((node.lineno, node.col_offset))

    def visit_Name(self, node: ast.Name) -> None:
        if self._inside and node.id == self.name:
            self.positions.add((node.lineno, node.col_offset))


def _find_target_function(tree: ast.AST, line: int) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == line
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one function at line {line}, found {len(matches)}")
    return matches[0]


def syntax_aware_local_rename(source: str, function_line: int, old_name: str, new_name: str) -> str:
    tree = ast.parse(source)
    target = _find_target_function(tree, function_line)
    all_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    all_names |= {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    if new_name in all_names or keyword.iskeyword(new_name):
        raise ValueError("replacement identifier is not fresh")
    collector = _ScopeNameCollector(target, old_name)
    collector.visit(target)
    if len(collector.positions) < 2:
        raise ValueError("rename target lacks declaration plus use")
    # AST columns count UTF-8 bytes; tokenize columns count Unicode characters.
    # Unicode separators inside literals are not Python physical newlines.
    lines = source.split("\n")
    positions = {
        (line, len(lines[line - 1].encode("utf-8")[:column].decode("utf-8")))
        for line, column in collector.positions
    }
    output: list[tokenize.TokenInfo] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and token.string == old_name and token.start in positions:
            token = tokenize.TokenInfo(token.type, new_name, token.start, token.end, token.line)
        output.append(token)
    transformed = tokenize.untokenize(output)
    ast.parse(transformed)
    compile(transformed, "<positive-control>", "exec")
    return transformed


def inert_trailing_comment(source: str) -> str:
    transformed = source + ("" if source.endswith("\n") else "\n") + "# inert audit marker\n"
    ast.parse(transformed)
    compile(transformed, "<positive-control>", "exec")
    return transformed


def scope_blind_identifier_collapse(source: str) -> str:
    output: list[tokenize.TokenInfo] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and not keyword.iskeyword(token.string):
            if token.string.startswith("__") and token.string.endswith("__"):
                output.append(token)
            else:
                output.append(tokenize.TokenInfo(token.type, "v", token.start, token.end, token.line))
        else:
            output.append(token)
    return tokenize.untokenize(output)


def _parse_compile(source: str) -> tuple[bool, bool, str]:
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return False, False, f"SyntaxError:{exc.msg}"
    try:
        compile(source, "<transfer-audit>", "exec")
    except Exception as exc:
        return True, False, f"{type(exc).__name__}:{exc}"
    return True, True, ""


def run_transfer_audit(corpus_root: Path, output: Path) -> dict[str, Any]:
    manifest = _read_csv(corpus_root / "transfer_manifest.csv")
    interventions: tuple[tuple[str, str, Callable[[str], str] | None], ...] = (
        ("inert-trailing-comment", "positive", inert_trailing_comment),
        ("syntax-aware-local-rename", "positive", None),
        ("scope-blind-identifier-collapse", "negative", scope_blind_identifier_collapse),
    )
    rows: list[dict[str, Any]] = []
    for record in manifest:
        source_path = corpus_root / "transfer" / record["project_slug"] / f"module-{int(record['selection_rank']):02d}.py"
        source = source_path.read_text(encoding="utf-8")
        if hashlib.sha256(source.encode()).hexdigest() != record["source_sha256"]:
            raise AssertionError(f"frozen source hash mismatch: {record['module_id']}")
        for intervention, role, transform in interventions:
            try:
                if intervention == "syntax-aware-local-rename":
                    candidate = syntax_aware_local_rename(
                        source,
                        int(record["rename_function_line"]),
                        record["rename_parameter"],
                        "cvlocal" + record["source_sha256"][:7],
                    )
                else:
                    assert transform is not None
                    candidate = transform(source)
                transform_error = ""
            except Exception as exc:
                candidate = source
                transform_error = f"{type(exc).__name__}:{exc}"
            parse_ok, compile_ok, error = _parse_compile(candidate)
            if transform_error:
                parse_ok = compile_ok = False
                error = transform_error
            rows.append(
                {
                    "project": record["project"],
                    "version": record["version"],
                    "module_id": record["module_id"],
                    "source_sha256": record["source_sha256"],
                    "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
                    "candidate_bytes": len(candidate.encode()),
                    "selection_rank": int(record["selection_rank"]),
                    "nonblank_lines": int(record["nonblank_lines"]),
                    "ast_nodes": int(record["ast_nodes"]),
                    "branch_nodes": int(record["branch_nodes"]),
                    "intervention": intervention,
                    "control_role": role,
                    "parse_ok": parse_ok,
                    "compile_ok": compile_ok,
                    "error_category": error,
                    "character_ngram_similarity": f"{_character_ngram_similarity(source, candidate):.12f}",
                    "token_multiset_similarity": f"{_token_multiset_similarity(source, candidate):.12f}",
                    "ast_profile_similarity": f"{_ast_profile_similarity(source, candidate):.12f}",
                }
            )
    _write_csv(output / "raw" / "project_transfer.csv", rows)

    summary_rows: list[dict[str, Any]] = []
    for intervention, role, _ in interventions:
        subset = [row for row in rows if row["intervention"] == intervention]
        successes = sum(bool(row["parse_ok"] and row["compile_ok"]) for row in subset)
        project_success = Counter()
        for row in subset:
            project_success[row["project"]] += int(bool(row["parse_ok"] and row["compile_ok"]))
        lower, upper = clopper_pearson(successes, len(subset))
        summary_rows.append(
            {
                "intervention": intervention,
                "control_role": role,
                "modules": len(subset),
                "parse_compile_successes": successes,
                "failures": len(subset) - successes,
                "projects_with_failure": sum(value < 5 for value in project_success.values()),
                "minimum_project_success": min(project_success.values()),
                "maximum_project_success": max(project_success.values()),
                "cp95_lower": f"{lower:.12f}",
                "cp95_upper": f"{upper:.12f}",
                "median_character_ngram_similarity": f"{median(float(row['character_ngram_similarity']) for row in subset):.12f}",
                "median_token_multiset_similarity": f"{median(float(row['token_multiset_similarity']) for row in subset):.12f}",
                "median_ast_profile_similarity": f"{median(float(row['ast_profile_similarity']) for row in subset):.12f}",
            }
        )
    _write_csv(output / "derived" / "project_transfer_summary.csv", summary_rows)

    negative = [row for row in rows if row["control_role"] == "negative"]
    ordered_modules = sorted(
        {(row["module_id"], int(row["ast_nodes"])) for row in negative},
        key=lambda item: (item[1], item[0]),
    )
    quartile = {module: min(index * 4 // len(ordered_modules) + 1, 4) for index, (module, _) in enumerate(ordered_modules)}
    size_rows: list[dict[str, Any]] = []
    for q in range(1, 5):
        subset = [row for row in negative if quartile[row["module_id"]] == q]
        nodes = [int(row["ast_nodes"]) for row in subset]
        successes = sum(bool(row["parse_ok"] and row["compile_ok"]) for row in subset)
        size_rows.append(
            {
                "ast_size_quartile": q,
                "modules": len(subset),
                "successes": successes,
                "failures": len(subset) - successes,
                "ast_nodes_min": min(nodes),
                "ast_nodes_max": max(nodes),
            }
        )
    _write_csv(output / "derived" / "project_transfer_size_strata.csv", size_rows)

    projects = sorted({row["project"] for row in negative})
    leave_rows: list[dict[str, Any]] = []
    for project in projects:
        subset = [row for row in negative if row["project"] != project]
        successes = sum(bool(row["parse_ok"] and row["compile_ok"]) for row in subset)
        leave_rows.append(
            {
                "held_out_project": project,
                "retained_modules": len(subset),
                "failures": len(subset) - successes,
                "success_rate": f"{successes / len(subset):.12f}",
            }
        )
    _write_csv(output / "derived" / "project_transfer_leave_one_project.csv", leave_rows)

    summary = {
        "projects": len(projects),
        "modules": len(manifest),
        "observations": len(rows),
        "summary": summary_rows,
        "negative_control_quartiles": size_rows,
        "negative_control_leave_one_project_failure_range": [
            min(int(row["failures"]) for row in leave_rows),
            max(int(row["failures"]) for row in leave_rows),
        ],
    }
    _write_json(output / "derived" / "project_transfer_summary.json", summary)
    return summary


def _family_means_from_rows(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, str], Fraction]:
    strata: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if row["attack"] not in DESTRUCTIVE_ATTACKS:
            continue
        key = (row["scheme"], row["attack"], str(row["severity"]))
        strata[key][0] += int(row["detected"])
        strata[key][1] += 1
    sums: dict[tuple[str, str], Fraction] = defaultdict(Fraction)
    counts: Counter[tuple[str, str]] = Counter()
    for (scheme, attack, _), (successes, trials) in strata.items():
        sums[(scheme, attack)] += Fraction(successes, trials)
        counts[(scheme, attack)] += 1
    return {key: sums[key] / counts[key] for key in sums}


def _mixture_scores(family: dict[tuple[str, str], Fraction], mixtures: dict[str, dict[str, float]]) -> dict[tuple[str, str], Fraction]:
    return {
        (mixture, scheme): sum(
            (Fraction(str(weight)) * family[(scheme, attack)] for attack, weight in weights.items()),
            Fraction(0, 1),
        )
        for mixture, weights in mixtures.items()
        for scheme in SCHEMES
    }


def generate_context_sensitivity(
    diagnostic_rows: Sequence[dict[str, Any]],
    intervention_rows: Sequence[dict[str, Any]],
    robustness_rows: Sequence[dict[str, Any]],
    mixtures: dict[str, dict[str, float]],
    output: Path,
    bootstrap_replicates: int = 5000,
    bootstrap_seed: int = 20260721,
) -> dict[str, Any]:
    tasks = sorted({str(row["task"]) for row in robustness_rows})
    languages = sorted({str(row["language"]) for row in robustness_rows})
    exclusions: list[tuple[str, str, Callable[[dict[str, Any]], bool]]] = []
    for task in tasks:
        exclusions.append(("task", task, lambda row, task=task: str(row["task"]) == task))
    for language in languages:
        exclusions.append(("language", language, lambda row, language=language: str(row["language"]) == language))
    for task in tasks:
        for language in languages:
            exclusions.append(
                (
                    "task-language",
                    f"{task}:{language}",
                    lambda row, task=task, language=language: str(row["task"]) == task and str(row["language"]) == language,
                )
            )

    holdout_rows: list[dict[str, Any]] = []
    for kind, label, excluded in exclusions:
        retained = [row for row in robustness_rows if not excluded(row)]
        scores = _mixture_scores(_family_means_from_rows(retained), mixtures)
        for mixture in mixtures:
            ranked = sorted(SCHEMES, key=lambda scheme: (-scores[(mixture, scheme)], scheme))
            ranks = {scheme: index + 1 for index, scheme in enumerate(ranked)}
            for scheme in SCHEMES:
                holdout_rows.append(
                    {
                        "holdout_kind": kind,
                        "held_out_context": label,
                        "mixture": mixture,
                        "scheme": scheme,
                        "score": f"{float(scores[(mixture, scheme)]):.12f}",
                        "rank": ranks[scheme],
                        "winner": ranked[0],
                    }
                )
    _write_csv(output / "derived" / "context_holdouts.csv", holdout_rows)

    # Precompute complete task-cluster rates, retaining both languages inside each task.
    cluster_counts: dict[tuple[str, str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in robustness_rows:
        if row["attack"] not in DESTRUCTIVE_ATTACKS:
            continue
        key = (str(row["task"]), str(row["scheme"]), str(row["attack"]), str(row["severity"]))
        cluster_counts[key][0] += int(row["detected"])
        cluster_counts[key][1] += 1
    cluster_rates = {key: Fraction(value[0], value[1]) for key, value in cluster_counts.items()}
    rng = random.Random(bootstrap_seed)
    bootstrap_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    winner_counts: Counter[tuple[str, str]] = Counter()
    score_samples: dict[tuple[str, str], list[float]] = defaultdict(list)
    gap_samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for replicate in range(bootstrap_replicates):
        sampled = [rng.choice(tasks) for _ in tasks]
        family: dict[tuple[str, str], Fraction] = {}
        for scheme in SCHEMES:
            for attack in DESTRUCTIVE_ATTACKS:
                total = sum(
                    (
                        cluster_rates[(task, scheme, attack, f"{severity:.1f}")]
                        for task in sampled
                        for severity in SEVERITIES
                    ),
                    Fraction(0, 1),
                )
                family[(scheme, attack)] = total / (len(sampled) * len(SEVERITIES))
        scores = _mixture_scores(family, mixtures)
        for mixture in mixtures:
            ranked = sorted(SCHEMES, key=lambda scheme: (-scores[(mixture, scheme)], scheme))
            winner_counts[(mixture, ranked[0])] += 1
            ranks = {scheme: index + 1 for index, scheme in enumerate(ranked)}
            for scheme in SCHEMES:
                value = float(scores[(mixture, scheme)])
                score_samples[(mixture, scheme)].append(value)
                bootstrap_rows.append(
                    {
                        "replicate": replicate,
                        "mixture": mixture,
                        "scheme": scheme,
                        "score": f"{value:.12f}",
                        "rank": ranks[scheme],
                        "winner": ranked[0],
                    }
                )
            for left_index, left in enumerate(SCHEMES):
                for right in SCHEMES[left_index + 1 :]:
                    gap = float(scores[(mixture, left)] - scores[(mixture, right)])
                    gap_samples[(mixture, left, right)].append(gap)
                    gap_rows.append(
                        {
                            "replicate": replicate,
                            "mixture": mixture,
                            "left_scheme": left,
                            "right_scheme": right,
                            "gap": f"{gap:.12f}",
                        }
                    )
    _write_csv(output / "derived" / "task_cluster_bootstrap.csv", bootstrap_rows)
    _write_csv(output / "derived" / "task_cluster_bootstrap_gaps.csv", gap_rows)

    bootstrap_summary: list[dict[str, Any]] = []
    for mixture in mixtures:
        for scheme in SCHEMES:
            values = score_samples[(mixture, scheme)]
            bootstrap_summary.append(
                {
                    "mixture": mixture,
                    "scheme": scheme,
                    "median_score": f"{_percentile(values, 0.50):.12f}",
                    "lower_95": f"{_percentile(values, 0.025):.12f}",
                    "upper_95": f"{_percentile(values, 0.975):.12f}",
                    "winner_probability": f"{winner_counts[(mixture, scheme)] / bootstrap_replicates:.12f}",
                }
            )
    _write_csv(output / "derived" / "task_cluster_bootstrap_summary.csv", bootstrap_summary)

    gap_summary: list[dict[str, Any]] = []
    for key in sorted(gap_samples):
        mixture, left, right = key
        values = gap_samples[key]
        gap_summary.append(
            {
                "mixture": mixture,
                "left_scheme": left,
                "right_scheme": right,
                "median_gap": f"{_percentile(values, 0.50):.12f}",
                "lower_95": f"{_percentile(values, 0.025):.12f}",
                "upper_95": f"{_percentile(values, 0.975):.12f}",
                "probability_left_exceeds_right": f"{sum(value > 0 for value in values) / len(values):.12f}",
            }
        )

    # Task and task-language AUCs expose concentration hidden by pooled contrasts.
    metric_names = sorted(key for key in diagnostic_rows[0] if key.endswith("_similarity"))
    auc_rows: list[dict[str, Any]] = []
    contexts: list[tuple[str, str, list[dict[str, Any]]]] = []
    for task in tasks:
        contexts.append(("task", task, [row for row in diagnostic_rows if str(row["task"]) == task]))
    for task in tasks:
        for language in languages:
            contexts.append(
                (
                    "task-language",
                    f"{task}:{language}",
                    [row for row in diagnostic_rows if str(row["task"]) == task and str(row["language"]) == language],
                )
            )
    for kind, label, rows in contexts:
        labels = [int(row["bounded_equivalent"]) for row in rows]
        indicators = [("nominal_test_pass_rate", [float(row["nominal_test_pass"]) for row in rows])]
        indicators += [(metric, [float(row[metric]) for row in rows]) for metric in metric_names]
        for indicator, scores in indicators:
            auc_rows.append(
                {
                    "context_kind": kind,
                    "context": label,
                    "indicator": indicator,
                    "rows": len(rows),
                    "roc_auc": f"{roc_auc(labels, scores):.12f}",
                }
            )
    _write_csv(output / "derived" / "contextual_semantic_proxy_auc.csv", auc_rows)

    # Match every intervention profile across the two independently implemented languages.
    distortion_names = sorted(key for key in intervention_rows[0] if key.endswith("_distortion"))
    indicators = distortion_names + ["carrier_retention", "payload_match_rate"]
    paired: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in intervention_rows:
        paired[(str(row["scheme"]), str(row["task"]), str(row["profile_id"]))][str(row["language"])] = row
    complete = [value for value in paired.values() if set(value) == {"python", "javascript"}]
    agreement_rows: list[dict[str, Any]] = []
    for indicator in indicators:
        left = [float(pair["python"][indicator]) for pair in complete]
        right = [float(pair["javascript"][indicator]) for pair in complete]
        differences = [abs(a - b) for a, b in zip(left, right)]
        agreement_rows.append(
            {
                "indicator": indicator,
                "matched_profiles": len(complete),
                "spearman": f"{spearman(left, right):.12f}",
                "median_absolute_difference": f"{median(differences):.12f}",
                "p95_absolute_difference": f"{_percentile(differences, 0.95):.12f}",
            }
        )
    _write_csv(output / "derived" / "cross_language_metric_agreement.csv", agreement_rows)

    summary = {
        "holdout_recomputations": len(exclusions),
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": bootstrap_seed,
        "bootstrap_summary": bootstrap_summary,
        "bootstrap_gap_summary": gap_summary,
        "contextual_auc_rows": len(auc_rows),
        "cross_language_metric_agreement": agreement_rows,
    }
    _write_json(output / "derived" / "context_sensitivity_summary.json", summary)
    return summary


def _tv_extreme(
    weights: dict[str, Fraction], values: dict[str, Fraction], rho: Fraction, minimize: bool
) -> tuple[Fraction, dict[str, Fraction]]:
    current = dict(weights)
    donors = sorted(values, key=lambda item: (values[item], item), reverse=minimize)
    recipients = sorted(values, key=lambda item: (values[item], item), reverse=not minimize)
    remaining = rho
    donor_index = recipient_index = 0
    while remaining > 0 and donor_index < len(donors) and recipient_index < len(recipients):
        donor = donors[donor_index]
        recipient = recipients[recipient_index]
        if donor == recipient or (minimize and values[donor] <= values[recipient]) or (not minimize and values[donor] >= values[recipient]):
            break
        movement = min(current[donor], 1 - current[recipient], remaining)
        if movement:
            current[donor] -= movement
            current[recipient] += movement
            remaining -= movement
        if current[donor] == 0:
            donor_index += 1
        if current[recipient] == 1:
            recipient_index += 1
    expectation = sum((current[key] * values[key] for key in values), Fraction(0, 1))
    return expectation, current


def _minimum_tv_to_tie(weights: dict[str, Fraction], differences: dict[str, Fraction]) -> tuple[Fraction, dict[str, Fraction]]:
    margin = sum((weights[key] * differences[key] for key in differences), Fraction(0, 1))
    if margin <= 0:
        return Fraction(0, 1), dict(weights)
    current = dict(weights)
    donors = sorted(differences, key=lambda item: (-differences[item], item))
    recipients = sorted(differences, key=lambda item: (differences[item], item))
    radius = Fraction(0, 1)
    donor_index = recipient_index = 0
    while margin > 0 and donor_index < len(donors) and recipient_index < len(recipients):
        donor = donors[donor_index]
        recipient = recipients[recipient_index]
        gap = differences[donor] - differences[recipient]
        if gap <= 0:
            raise ValueError("positive margin cannot be removed")
        movement = min(current[donor], 1 - current[recipient], margin / gap)
        if movement <= 0:
            if current[donor] == 0:
                donor_index += 1
            if current[recipient] == 1:
                recipient_index += 1
            continue
        current[donor] -= movement
        current[recipient] += movement
        radius += movement
        margin -= movement * gap
        if current[donor] == 0:
            donor_index += 1
        if current[recipient] == 1:
            recipient_index += 1
    if margin != 0:
        raise ValueError("failed to construct exact tie")
    return radius, current


def generate_ambiguity_analysis(
    robustness_rows: Sequence[dict[str, Any]],
    mixtures: dict[str, dict[str, float]],
    output: Path,
) -> dict[str, Any]:
    family = _family_means_from_rows(robustness_rows)
    radii = [Fraction(0, 1), Fraction(1, 100), Fraction(5, 100), Fraction(1, 10), Fraction(1, 5), Fraction(3, 10), Fraction(1, 2)]
    envelope_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    robust_rows: list[dict[str, Any]] = []
    for mixture, raw_weights in mixtures.items():
        weights = {attack: Fraction(str(weight)) for attack, weight in raw_weights.items()}
        for scheme in SCHEMES:
            values = {attack: family[(scheme, attack)] for attack in weights}
            baseline = sum((weights[attack] * values[attack] for attack in weights), Fraction(0, 1))
            for rho in radii:
                lower, _ = _tv_extreme(weights, values, rho, minimize=True)
                upper, _ = _tv_extreme(weights, values, rho, minimize=False)
                envelope_rows.append(
                    {
                        "mixture": mixture,
                        "scheme": scheme,
                        "tv_radius": f"{float(rho):.2f}",
                        "baseline_score": f"{float(baseline):.12f}",
                        "worst_case_score": f"{float(lower):.12f}",
                        "best_case_score": f"{float(upper):.12f}",
                    }
                )
        scores = {
            scheme: sum((weights[a] * family[(scheme, a)] for a in weights), Fraction(0, 1))
            for scheme in SCHEMES
        }
        for left_index, left in enumerate(SCHEMES):
            for right in SCHEMES[left_index + 1 :]:
                difference = {attack: family[(left, attack)] - family[(right, attack)] for attack in weights}
                margin = scores[left] - scores[right]
                if margin >= 0:
                    winner, challenger = left, right
                    radius, witness = _minimum_tv_to_tie(weights, difference)
                else:
                    winner, challenger = right, left
                    radius, witness = _minimum_tv_to_tie(weights, {key: -value for key, value in difference.items()})
                absolute_margin = abs(margin)
                pair_rows.append(
                    {
                        "mixture": mixture,
                        "winner": winner,
                        "challenger": challenger,
                        "baseline_margin": f"{float(absolute_margin):.12f}",
                        "baseline_margin_exact": f"{absolute_margin.numerator}/{absolute_margin.denominator}",
                        "minimum_tv_to_tie": f"{float(radius):.12f}",
                        "minimum_tv_to_tie_exact": f"{radius.numerator}/{radius.denominator}",
                        "tie_weights": json.dumps({k: f"{float(v):.12f}" for k, v in sorted(witness.items())}, sort_keys=True),
                        "tie_weights_exact": json.dumps({k: f"{v.numerator}/{v.denominator}" for k, v in sorted(witness.items())}, sort_keys=True),
                    }
                )
        for rho in radii:
            certified: list[str] = []
            for candidate in SCHEMES:
                if all(
                    _tv_extreme(
                        weights,
                        {attack: family[(candidate, attack)] - family[(challenger, attack)] for attack in weights},
                        rho,
                        minimize=True,
                    )[0]
                    > 0
                    for challenger in SCHEMES
                    if challenger != candidate
                ):
                    certified.append(candidate)
            robust_rows.append(
                {
                    "mixture": mixture,
                    "tv_radius": f"{float(rho):.2f}",
                    "certified_strict_winners": "|".join(certified) if certified else "indeterminate",
                }
            )
    _write_csv(output / "derived" / "mixture_ambiguity_envelopes.csv", envelope_rows)
    _write_csv(output / "derived" / "pairwise_mixture_stability.csv", pair_rows)
    _write_csv(output / "derived" / "mixture_robust_winner_sets.csv", robust_rows)
    summary = {
        "envelope_rows": len(envelope_rows),
        "pairwise_rows": len(pair_rows),
        "robust_winner_rows": len(robust_rows),
        "pairwise": pair_rows,
        "robust_sets": robust_rows,
    }
    _write_json(output / "derived" / "mixture_ambiguity_summary.json", summary)
    return summary


def generate_decision_functional_sensitivity(
    robustness_rows: Sequence[dict[str, Any]], output: Path
) -> dict[str, Any]:
    family = _family_means_from_rows(robustness_rows)
    rows: list[dict[str, Any]] = []
    values: dict[str, dict[str, float]] = defaultdict(dict)
    for scheme in SCHEMES:
        vector = [family[(scheme, attack)] for attack in DESTRUCTIVE_ATTACKS]
        arithmetic = float(sum(vector, Fraction(0, 1)) / len(vector))
        geometric = math.prod(float(value) for value in vector) ** (1 / len(vector))
        median_value = float(sorted(vector)[len(vector) // 2])
        worst = float(min(vector))
        share = sum(value >= Fraction(3, 10) for value in vector) / len(vector)
        values["equal-family arithmetic mean"][scheme] = arithmetic
        values["equal-family geometric mean"][scheme] = geometric
        values["median family rate"][scheme] = median_value
        values["worst family rate"][scheme] = worst
        values["share of families at or above 0.30"][scheme] = share
    winners: dict[str, str] = {}
    for functional in (
        "equal-family arithmetic mean",
        "equal-family geometric mean",
        "median family rate",
        "worst family rate",
        "share of families at or above 0.30",
    ):
        ranked = sorted(SCHEMES, key=lambda scheme: (-values[functional][scheme], scheme))
        winners[functional] = ranked[0]
        ranks = {scheme: index + 1 for index, scheme in enumerate(ranked)}
        for scheme in SCHEMES:
            rows.append(
                {
                    "functional": functional,
                    "scheme": scheme,
                    "score": f"{values[functional][scheme]:.12f}",
                    "rank": ranks[scheme],
                    "winner": ranked[0],
                }
            )
    _write_csv(output / "derived" / "decision_functional_sensitivity.csv", rows)
    summary = {
        "functionals": len(winners),
        "rows": len(rows),
        "winners": winners,
        "distinct_winners": sorted(set(winners.values())),
    }
    _write_json(output / "derived" / "decision_functional_sensitivity.json", summary)
    return summary
