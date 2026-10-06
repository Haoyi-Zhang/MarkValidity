"""Independent reconstruction of the extended validity and transfer analyses."""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import keyword
import math
import random
import re
import tokenize
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import median
from typing import Any, Callable, Sequence

SCHEMES = ("lexical", "structural", "hybrid")
ATTACKS = ("format", "rename", "normalize", "random_flip", "strip", "mixed")
DESTRUCTIVE = ("rename", "normalize", "random_flip", "strip", "mixed")
SEVERITIES = tuple(f"{index / 10:.1f}" for index in range(11))
MIXTURES = {
    "balanced": {attack: Fraction(1, 5) for attack in DESTRUCTIVE},
    "rename-heavy": {
        "rename": Fraction(54, 100), "normalize": Fraction(0),
        "random_flip": Fraction(24, 100), "strip": Fraction(22, 100), "mixed": Fraction(0),
    },
    "structure-heavy": {
        "rename": Fraction(0), "normalize": Fraction(54, 100),
        "random_flip": Fraction(24, 100), "strip": Fraction(22, 100), "mixed": Fraction(0),
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_bool(value: str) -> bool:
    return value.lower() in {"true", "1"}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    positives = [score for label, score in zip(labels, scores) if label == 1]
    negatives = [score for label, score in zip(labels, scores) if label == 0]
    total = 0.0
    for positive in positives:
        for negative in negatives:
            total += 1.0 if positive > negative else 0.5 if positive == negative else 0.0
    return total / (len(positives) * len(negatives))


def ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    output = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        average = (cursor + 1 + end) / 2
        for position in range(cursor, end):
            output[order[position]] = average
        cursor = end
    return output


def spearman(left: Sequence[float], right: Sequence[float]) -> float:
    x, y = ranks(left), ranks(right)
    mx, my = sum(x) / len(x), sum(y) / len(y)
    numerator = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = sum((a - mx) ** 2 for a in x)
    dy = sum((b - my) ** 2 for b in y)
    return 0.0 if dx == 0 or dy == 0 else numerator / math.sqrt(dx * dy)


def weighted_jaccard(left: Counter[Any], right: Counter[Any]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 1.0
    return sum(min(left[key], right[key]) for key in keys) / sum(max(left[key], right[key]) for key in keys)


def lexical_tokens(source: str) -> list[str]:
    """Reconstruct the released language-neutral token profile independently."""
    token_pattern = re.compile(
        r"[A-Za-z_$][A-Za-z0-9_$]*|"
        r"(?:\d+\.\d+|\d+)|"
        r"(?:===|!==|==|!=|<=|>=|=>|\+\+|--|&&|\|\||\*\*|//)|"
        r"[{}()\[\];,.?:+\-*/%<>=]"
    )
    without_comments = "\n".join(line.split("#", 1)[0] for line in source.splitlines())
    return token_pattern.findall(without_comments)


def character_similarity(left: str, right: str, width: int = 5) -> float:
    def grams(value: str) -> Counter[str]:
        if len(value) < width:
            return Counter(value)
        return Counter(value[index:index + width] for index in range(len(value) - width + 1))
    return weighted_jaccard(grams(left), grams(right))


def ast_similarity(left: str, right: str) -> float:
    def profile(value: str) -> Counter[str]:
        try:
            return Counter(type(node).__name__ for node in ast.walk(ast.parse(value)))
        except SyntaxError:
            return Counter({"PARSE_FAILURE": 1})
    return weighted_jaccard(profile(left), profile(right))


class ScopeCollector(ast.NodeVisitor):
    def __init__(self, target: ast.AST, name: str) -> None:
        self.target, self.name = target, name
        self.inside = False
        self.positions: set[tuple[int, int]] = set()

    def visit(self, node: ast.AST) -> Any:
        if node is self.target:
            old = self.inside
            self.inside = True
            result = super().visit(node)
            self.inside = old
            return result
        if self.inside and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return None
        return super().visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        if self.inside and node.arg == self.name:
            self.positions.add((node.lineno, node.col_offset))

    def visit_Name(self, node: ast.Name) -> None:
        if self.inside and node.id == self.name:
            self.positions.add((node.lineno, node.col_offset))


def local_rename(source: str, function_line: int, old_name: str, new_name: str) -> str:
    tree = ast.parse(source)
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == function_line]
    if len(functions) != 1:
        raise ValueError("target function not unique")
    all_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
    if new_name in all_names or keyword.iskeyword(new_name):
        raise ValueError("replacement not fresh")
    collector = ScopeCollector(functions[0], old_name)
    collector.visit(functions[0])
    if len(collector.positions) < 2:
        raise ValueError("insufficient rename positions")
    lines = source.split("\n")
    character_positions = set()
    for line, byte_column in collector.positions:
        prefix = lines[line - 1].encode("utf-8")[:byte_column].decode("utf-8")
        character_positions.add((line, len(prefix)))
    output: list[tokenize.TokenInfo] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and token.string == old_name and token.start in character_positions:
            token = tokenize.TokenInfo(token.type, new_name, token.start, token.end, token.line)
        output.append(token)
    return tokenize.untokenize(output)


def collapse(source: str) -> str:
    output: list[tokenize.TokenInfo] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and not keyword.iskeyword(token.string) and not (token.string.startswith("__") and token.string.endswith("__")):
            token = tokenize.TokenInfo(token.type, "v", token.start, token.end, token.line)
        output.append(token)
    return tokenize.untokenize(output)


def parse_compile(source: str) -> tuple[bool, bool, str]:
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return False, False, f"SyntaxError:{exc.msg}"
    try:
        compile(source, "<transfer-audit>", "exec")
    except Exception as exc:
        return True, False, f"{type(exc).__name__}:{exc}"
    return True, True, ""


def binomial_cdf(n: int, x: int, p: float) -> float:
    return sum(math.comb(n, k) * (p**k) * ((1 - p) ** (n - k)) for k in range(x + 1))


def binomial_upper(n: int, x: int, p: float) -> float:
    return sum(math.comb(n, k) * (p**k) * ((1 - p) ** (n - k)) for k in range(x, n + 1))


def clopper_pearson(x: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if x == 0:
        lower = 0.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if binomial_upper(n, x, mid) > alpha / 2:
                hi = mid
            else:
                lo = mid
        lower = (lo + hi) / 2
    if x == n:
        upper = 1.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if binomial_cdf(n, x, mid) > alpha / 2:
                lo = mid
            else:
                hi = mid
        upper = (lo + hi) / 2
    return lower, upper


def family_means(rows: Sequence[dict[str, str]]) -> dict[tuple[str, str], Fraction]:
    counts: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if row["attack"] not in DESTRUCTIVE:
            continue
        key = (row["scheme"], row["attack"], row["severity"])
        counts[key][0] += int(row["detected"])
        counts[key][1] += 1
    totals: dict[tuple[str, str], Fraction] = defaultdict(Fraction)
    number: Counter[tuple[str, str]] = Counter()
    for (scheme, attack, _), (successes, trials) in counts.items():
        totals[(scheme, attack)] += Fraction(successes, trials)
        number[(scheme, attack)] += 1
    return {key: totals[key] / number[key] for key in totals}


def mixture_scores(family: dict[tuple[str, str], Fraction]) -> dict[tuple[str, str], Fraction]:
    return {
        (mixture, scheme): sum((weight * family[(scheme, attack)] for attack, weight in weights.items()), Fraction(0))
        for mixture, weights in MIXTURES.items() for scheme in SCHEMES
    }


def tv_extreme(weights: dict[str, Fraction], values: dict[str, Fraction], rho: Fraction, minimize: bool) -> Fraction:
    current = dict(weights)
    donors = sorted(values, key=lambda key: (values[key], key), reverse=minimize)
    recipients = sorted(values, key=lambda key: (values[key], key), reverse=not minimize)
    remaining = rho
    di = ri = 0
    while remaining > 0 and di < len(donors) and ri < len(recipients):
        donor, recipient = donors[di], recipients[ri]
        if donor == recipient or (minimize and values[donor] <= values[recipient]) or (not minimize and values[donor] >= values[recipient]):
            break
        movement = min(current[donor], 1 - current[recipient], remaining)
        current[donor] -= movement
        current[recipient] += movement
        remaining -= movement
        if current[donor] == 0:
            di += 1
        if current[recipient] == 1:
            ri += 1
    return sum((current[key] * values[key] for key in values), Fraction(0))


def tv_distance(left: dict[str, Fraction], right: dict[str, Fraction]) -> Fraction:
    return sum((abs(left[key] - right[key]) for key in left), Fraction(0)) / 2


def recheck_extended(results: Path, findings: list[dict[str, Any]], require: Callable[..., None]) -> None:
    # --results may point outside this artifact; the licensed corpus belongs
    # to the checker source tree, not to an arbitrary output parent.
    artifact = Path(__file__).resolve().parent
    summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    require(summary["project_transfer"]["projects"] == 24, "extended::transfer_projects", findings)
    require(summary["project_transfer"]["modules"] == 120, "extended::transfer_modules", findings)
    require(summary["project_transfer"]["observations"] == 360, "extended::transfer_observations", findings)
    require(summary["context_sensitivity"] == {"holdout_recomputations": 38, "bootstrap_replicates": 5000, "contextual_auc_rows": 288}, "extended::context_summary", findings, summary["context_sensitivity"])
    require(summary["mixture_ambiguity"] == {"envelope_rows": 63, "pairwise_rows": 9, "robust_winner_rows": 21}, "extended::ambiguity_summary", findings)
    require(summary["decision_functional_sensitivity"]["functionals"] == 5, "extended::decision_functionals", findings)

    manifest = read_csv(artifact / "corpus/transfer_manifest.csv")
    require(len(manifest) == 120, "transfer::manifest_rows", findings)
    require(len({row["project"] for row in manifest}) == 24, "transfer::manifest_projects", findings)
    require(all(value == 5 for value in Counter(row["project"] for row in manifest).values()), "transfer::five_per_project", findings)
    frozen_sources: dict[str, tuple[str, dict[str, str]]] = {}
    for record in manifest:
        path = artifact / "corpus/transfer" / record["project_slug"] / f"module-{int(record['selection_rank']):02d}.py"
        source = path.read_text(encoding="utf-8")
        require(sha256_text(source) == record["source_sha256"], f"transfer::source_hash::{record['module_id']}", findings)
        frozen_sources[record["module_id"]] = (source, record)

    transfer = read_csv(results / "raw/project_transfer.csv")
    require(len(transfer) == 360, "transfer::rows", findings)
    lookup = {(row["module_id"], row["intervention"]): row for row in transfer}
    require(len(lookup) == 360, "transfer::unique_keys", findings)
    recreated_ok = True
    first_problem = ""
    for module_id, (source, record) in frozen_sources.items():
        candidates: dict[str, str] = {}
        candidates["inert-trailing-comment"] = source + ("" if source.endswith("\n") else "\n") + "# inert audit marker\n"
        candidates["syntax-aware-local-rename"] = local_rename(source, int(record["rename_function_line"]), record["rename_parameter"], "cvlocal" + record["source_sha256"][:7])
        candidates["scope-blind-identifier-collapse"] = collapse(source)
        for intervention, candidate in candidates.items():
            row = lookup[(module_id, intervention)]
            parse_ok, compile_ok, error = parse_compile(candidate)
            expected = {
                "candidate_sha256": sha256_text(candidate),
                "candidate_bytes": str(len(candidate.encode())),
                "parse_ok": str(parse_ok),
                "compile_ok": str(compile_ok),
                "error_category": error,
                "character_ngram_similarity": f"{character_similarity(source, candidate):.12f}",
                "token_multiset_similarity": f"{weighted_jaccard(Counter(lexical_tokens(source)), Counter(lexical_tokens(candidate))):.12f}",
                "ast_profile_similarity": f"{ast_similarity(source, candidate):.12f}",
            }
            if any(row[key] != value for key, value in expected.items()):
                recreated_ok = False
                first_problem = f"{module_id}:{intervention}"
                break
        if not recreated_ok:
            break
    require(recreated_ok, "transfer::candidate_reconstruction", findings, first_problem)

    summary_rows = read_csv(results / "derived/project_transfer_summary.csv")
    summary_ok = True
    for row in summary_rows:
        subset = [value for value in transfer if value["intervention"] == row["intervention"]]
        successes = sum(as_bool(value["parse_ok"]) and as_bool(value["compile_ok"]) for value in subset)
        project_success = Counter()
        for value in subset:
            project_success[value["project"]] += int(as_bool(value["parse_ok"]) and as_bool(value["compile_ok"]))
        lower, upper = clopper_pearson(successes, len(subset))
        checks = {
            "modules": str(len(subset)), "parse_compile_successes": str(successes),
            "failures": str(len(subset) - successes),
            "projects_with_failure": str(sum(value < 5 for value in project_success.values())),
            "minimum_project_success": str(min(project_success.values())),
            "maximum_project_success": str(max(project_success.values())),
            "cp95_lower": f"{lower:.12f}", "cp95_upper": f"{upper:.12f}",
            "median_character_ngram_similarity": f"{median(float(value['character_ngram_similarity']) for value in subset):.12f}",
            "median_token_multiset_similarity": f"{median(float(value['token_multiset_similarity']) for value in subset):.12f}",
            "median_ast_profile_similarity": f"{median(float(value['ast_profile_similarity']) for value in subset):.12f}",
        }
        summary_ok &= all(row[key] == expected for key, expected in checks.items())
    require(summary_ok, "transfer::summary_reconstruction", findings)

    robustness = read_csv(results / "raw/robustness.csv")
    tasks = sorted({row["task"] for row in robustness})
    languages = sorted({row["language"] for row in robustness})
    holdout_rows = read_csv(results / "derived/context_holdouts.csv")
    holdout_lookup = {(row["holdout_kind"], row["held_out_context"], row["mixture"], row["scheme"]): row for row in holdout_rows}
    require(len(holdout_rows) == 342 and len(holdout_lookup) == 342, "context::holdout_rows", findings)
    contexts: list[tuple[str, str, Callable[[dict[str, str]], bool]]] = []
    contexts += [("task", task, lambda row, task=task: row["task"] == task) for task in tasks]
    contexts += [("language", language, lambda row, language=language: row["language"] == language) for language in languages]
    contexts += [("task-language", f"{task}:{language}", lambda row, task=task, language=language: row["task"] == task and row["language"] == language) for task in tasks for language in languages]
    holdout_ok = True
    for kind, label, exclude in contexts:
        scores = mixture_scores(family_means([row for row in robustness if not exclude(row)]))
        for mixture in MIXTURES:
            ranked = sorted(SCHEMES, key=lambda scheme: (-scores[(mixture, scheme)], scheme))
            for index, scheme in enumerate(ranked, 1):
                row = holdout_lookup[(kind, label, mixture, scheme)]
                holdout_ok &= row["score"] == f"{float(scores[(mixture, scheme)]):.12f}" and row["rank"] == str(index) and row["winner"] == ranked[0]
    require(holdout_ok, "context::holdout_reconstruction", findings)

    cluster_counts: dict[tuple[str, str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in robustness:
        if row["attack"] not in DESTRUCTIVE:
            continue
        key = (row["task"], row["scheme"], row["attack"], row["severity"])
        cluster_counts[key][0] += int(row["detected"])
        cluster_counts[key][1] += 1
    cluster_rates = {key: Fraction(value[0], value[1]) for key, value in cluster_counts.items()}
    bootstrap = read_csv(results / "derived/task_cluster_bootstrap.csv")
    bootstrap_lookup = {(int(row["replicate"]), row["mixture"], row["scheme"]): row for row in bootstrap}
    require(len(bootstrap) == 45000 and len(bootstrap_lookup) == 45000, "context::bootstrap_rows", findings)
    rng = random.Random(20260721)
    bootstrap_ok = True
    winner_counts: Counter[tuple[str, str]] = Counter()
    samples: dict[tuple[str, str], list[float]] = defaultdict(list)
    gap_samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for replicate in range(5000):
        sampled = [rng.choice(tasks) for _ in tasks]
        family: dict[tuple[str, str], Fraction] = {}
        for scheme in SCHEMES:
            for attack in DESTRUCTIVE:
                total = sum((cluster_rates[(task, scheme, attack, severity)] for task in sampled for severity in SEVERITIES), Fraction(0))
                family[(scheme, attack)] = total / (len(sampled) * len(SEVERITIES))
        scores = mixture_scores(family)
        for mixture in MIXTURES:
            ranked = sorted(SCHEMES, key=lambda scheme: (-scores[(mixture, scheme)], scheme))
            winner_counts[(mixture, ranked[0])] += 1
            for rank, scheme in enumerate(ranked, 1):
                value = float(scores[(mixture, scheme)])
                row = bootstrap_lookup[(replicate, mixture, scheme)]
                bootstrap_ok &= row["score"] == f"{value:.12f}" and row["rank"] == str(rank) and row["winner"] == ranked[0]
                samples[(mixture, scheme)].append(value)
            for left_index, left in enumerate(SCHEMES):
                for right in SCHEMES[left_index + 1:]:
                    gap_samples[(mixture, left, right)].append(float(scores[(mixture, left)] - scores[(mixture, right)]))
    require(bootstrap_ok, "context::bootstrap_reconstruction", findings)
    bootstrap_summary = read_csv(results / "derived/task_cluster_bootstrap_summary.csv")
    summary_lookup = {(row["mixture"], row["scheme"]): row for row in bootstrap_summary}
    summary_ok = True
    for key, values in samples.items():
        row = summary_lookup[key]
        mixture, scheme = key
        summary_ok &= row["median_score"] == f"{percentile(values,.5):.12f}"
        summary_ok &= row["lower_95"] == f"{percentile(values,.025):.12f}"
        summary_ok &= row["upper_95"] == f"{percentile(values,.975):.12f}"
        summary_ok &= row["winner_probability"] == f"{winner_counts[(mixture,scheme)]/5000:.12f}"
    require(summary_ok, "context::bootstrap_summary", findings)

    diagnostics = read_csv(results / "raw/diagnostic_pairs.csv")
    auc_rows = read_csv(results / "derived/contextual_semantic_proxy_auc.csv")
    auc_lookup = {(row["context_kind"], row["context"], row["indicator"]): row for row in auc_rows}
    metric_names = sorted(key for key in diagnostics[0] if key.endswith("_similarity"))
    auc_ok = True
    for kind, label, subset in (
        [("task", task, [row for row in diagnostics if row["task"] == task]) for task in tasks]
        + [("task-language", f"{task}:{language}", [row for row in diagnostics if row["task"] == task and row["language"] == language]) for task in tasks for language in languages]
    ):
        labels = [int(row["bounded_equivalent"]) for row in subset]
        indicators = [("nominal_test_pass_rate", [float(row["nominal_test_pass"]) for row in subset])]
        indicators += [(metric, [float(row[metric]) for row in subset]) for metric in metric_names]
        for indicator, scores in indicators:
            row = auc_lookup[(kind, label, indicator)]
            auc_ok &= row["rows"] == str(len(subset)) and row["roc_auc"] == f"{roc_auc(labels,scores):.12f}"
    require(len(auc_rows) == 288 and auc_ok, "context::auc_reconstruction", findings)

    interventions = read_csv(results / "raw/metric_interventions.csv")
    paired: dict[tuple[str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in interventions:
        paired[(row["scheme"], row["task"], row["profile_id"])][row["language"]] = row
    complete = [value for value in paired.values() if set(value) == {"python", "javascript"}]
    agreement = read_csv(results / "derived/cross_language_metric_agreement.csv")
    agreement_lookup = {row["indicator"]: row for row in agreement}
    indicators = sorted(key for key in interventions[0] if key.endswith("_distortion")) + ["carrier_retention", "payload_match_rate"]
    agreement_ok = True
    for indicator in indicators:
        left = [float(pair["python"][indicator]) for pair in complete]
        right = [float(pair["javascript"][indicator]) for pair in complete]
        differences = [abs(a-b) for a,b in zip(left,right)]
        row = agreement_lookup[indicator]
        agreement_ok &= row["matched_profiles"] == str(len(complete))
        agreement_ok &= row["spearman"] == f"{spearman(left,right):.12f}"
        agreement_ok &= row["median_absolute_difference"] == f"{median(differences):.12f}"
        agreement_ok &= row["p95_absolute_difference"] == f"{percentile(differences,.95):.12f}"
    require(len(agreement) == 9 and agreement_ok, "context::cross_language_agreement", findings)

    family = family_means(robustness)
    envelopes = read_csv(results / "derived/mixture_ambiguity_envelopes.csv")
    envelope_ok = len(envelopes) == 63
    for row in envelopes:
        weights = MIXTURES[row["mixture"]]
        values = {attack: family[(row["scheme"], attack)] for attack in weights}
        rho = Fraction(row["tv_radius"])
        baseline = sum((weights[a] * values[a] for a in weights), Fraction(0))
        envelope_ok &= row["baseline_score"] == f"{float(baseline):.12f}"
        envelope_ok &= row["worst_case_score"] == f"{float(tv_extreme(weights,values,rho,True)):.12f}"
        envelope_ok &= row["best_case_score"] == f"{float(tv_extreme(weights,values,rho,False)):.12f}"
    require(envelope_ok, "ambiguity::envelopes", findings)

    pairwise = read_csv(results / "derived/pairwise_mixture_stability.csv")
    pairwise_ok = len(pairwise) == 9
    for row in pairwise:
        weights = MIXTURES[row["mixture"]]
        witness = {key: Fraction(value) for key, value in json.loads(row["tie_weights_exact"]).items()}
        distance = tv_distance(weights, witness)
        winner, challenger = row["winner"], row["challenger"]
        margin = abs(sum((weights[a] * (family[(winner,a)]-family[(challenger,a)]) for a in weights), Fraction(0)))
        tie = sum((witness[a] * (family[(winner,a)]-family[(challenger,a)]) for a in witness), Fraction(0))
        pairwise_ok &= sum(witness.values(), Fraction(0)) == 1 and all(value >= 0 for value in witness.values())
        pairwise_ok &= row["baseline_margin_exact"] == f"{margin.numerator}/{margin.denominator}"
        pairwise_ok &= row["minimum_tv_to_tie_exact"] == f"{distance.numerator}/{distance.denominator}"
        pairwise_ok &= row["baseline_margin"] == f"{float(margin):.12f}" and row["minimum_tv_to_tie"] == f"{float(distance):.12f}"
        pairwise_ok &= tie == 0
        differences = {attack: family[(winner,attack)]-family[(challenger,attack)] for attack in weights}
        pairwise_ok &= tv_extreme(weights,differences,distance,True) == 0
    require(pairwise_ok, "ambiguity::pairwise_exact_witnesses", findings)

    robust_sets = read_csv(results / "derived/mixture_robust_winner_sets.csv")
    robust_ok = len(robust_sets) == 21
    for row in robust_sets:
        weights = MIXTURES[row["mixture"]]
        rho = Fraction(row["tv_radius"])
        certified = []
        for candidate in SCHEMES:
            if all(tv_extreme(weights,{attack:family[(candidate,attack)]-family[(challenger,attack)] for attack in weights},rho,True)>0 for challenger in SCHEMES if challenger!=candidate):
                certified.append(candidate)
        robust_ok &= row["certified_strict_winners"] == ("|".join(certified) if certified else "indeterminate")
    require(robust_ok, "ambiguity::robust_winner_sets", findings)

    functional_rows = read_csv(results / "derived/decision_functional_sensitivity.csv")
    expected: dict[str, dict[str, float]] = defaultdict(dict)
    for scheme in SCHEMES:
        vector = [family[(scheme,attack)] for attack in DESTRUCTIVE]
        expected["equal-family arithmetic mean"][scheme] = float(sum(vector,Fraction(0))/5)
        expected["equal-family geometric mean"][scheme] = math.prod(float(value) for value in vector)**.2
        expected["median family rate"][scheme] = float(sorted(vector)[2])
        expected["worst family rate"][scheme] = float(min(vector))
        expected["share of families at or above 0.30"][scheme] = sum(value>=Fraction(3,10) for value in vector)/5
    functional_ok = len(functional_rows)==15
    lookup = {(row["functional"],row["scheme"]):row for row in functional_rows}
    winners=set()
    for functional, scores in expected.items():
        ranked=sorted(SCHEMES,key=lambda scheme:(-scores[scheme],scheme)); winners.add(ranked[0])
        for rank,scheme in enumerate(ranked,1):
            row=lookup[(functional,scheme)]
            functional_ok &= row["score"]==f"{scores[scheme]:.12f}" and row["rank"]==str(rank) and row["winner"]==ranked[0]
    require(functional_ok and len(winners)>=2, "decision_functionals::reconstruction_and_rank_change", findings, sorted(winners))
