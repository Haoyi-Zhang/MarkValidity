
from __future__ import annotations

import ast
import difflib
import math
import re
from collections import Counter
from math import comb
from typing import Iterable, Sequence

PY_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
}
JS_KEYWORDS = {
    "break", "case", "catch", "class", "const", "continue", "debugger", "default",
    "delete", "do", "else", "export", "extends", "false", "finally", "for",
    "function", "if", "import", "in", "instanceof", "let", "new", "null",
    "return", "super", "switch", "this", "throw", "true", "try", "typeof",
    "var", "void", "while", "with", "yield",
}
TOKEN_RE = re.compile(
    r"[A-Za-z_$][A-Za-z0-9_$]*|"
    r"(?:\d+\.\d+|\d+)|"
    r"(?:===|!==|==|!=|<=|>=|=>|\+\+|--|&&|\|\||\*\*|//)|"
    r"[{}()\[\];,.?:+\-*/%<>=]"
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
NUMBER_RE = re.compile(r"^(?:\d+\.\d+|\d+)$")


def _strip_comments(source: str, language: str) -> str:
    if language == "python":
        return "\n".join(line.split("#", 1)[0] for line in source.splitlines())
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def tokens(source: str, language: str) -> list[str]:
    return TOKEN_RE.findall(_strip_comments(source, language))


def identifiers(source: str, language: str) -> list[str]:
    keywords = PY_KEYWORDS if language == "python" else JS_KEYWORDS
    return [
        token for token in tokens(source, language)
        if IDENTIFIER_RE.match(token) and token not in keywords
    ]


def _sequence_similarity(left: Sequence[str] | str, right: Sequence[str] | str) -> float:
    return difflib.SequenceMatcher(a=left, b=right, autojunk=False).ratio()


def _weighted_jaccard(left: Counter, right: Counter) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 1.0
    numerator = sum(min(left[key], right[key]) for key in keys)
    denominator = sum(max(left[key], right[key]) for key in keys)
    return numerator / denominator if denominator else 1.0


def _normalized_tokens(source: str, language: str) -> list[str]:
    keywords = PY_KEYWORDS if language == "python" else JS_KEYWORDS
    normalized: list[str] = []
    for token in tokens(source, language):
        if IDENTIFIER_RE.match(token) and token not in keywords:
            normalized.append("<ID>")
        elif NUMBER_RE.match(token):
            normalized.append("<NUM>")
        else:
            normalized.append(token)
    return normalized


def _python_ast_profile(source: str) -> Counter:
    tree = ast.parse(source)
    return Counter(type(node).__name__ for node in ast.walk(tree))


def _javascript_syntactic_profile(source: str) -> Counter:
    clean = _strip_comments(source, "javascript")
    toks = tokens(clean, "javascript")
    profile: Counter = Counter()
    mappings = {
        "function": "FunctionDeclaration",
        "return": "ReturnStatement",
        "if": "IfStatement",
        "for": "ForStatement",
        "while": "WhileStatement",
        "const": "VariableDeclaration",
        "let": "VariableDeclaration",
        "throw": "ThrowStatement",
    }
    for token in toks:
        if token in mappings:
            profile[mappings[token]] += 1
        elif token in {"+", "-", "*", "/", "%", "**"}:
            profile["BinaryExpression"] += 1
        elif token in {"==", "!=", "===", "!==", "<", ">", "<=", ">="}:
            profile["ComparisonExpression"] += 1
        elif token in {"&&", "||"}:
            profile["LogicalExpression"] += 1
        elif token == "=":
            profile["AssignmentExpression"] += 1
        elif token == "[":
            profile["ArrayExpression"] += 1
        elif token == "{":
            profile["BlockOrObject"] += 1
    for index, token in enumerate(toks[:-1]):
        if IDENTIFIER_RE.match(token) and toks[index + 1] == "(" and token not in JS_KEYWORDS:
            profile["CallExpression"] += 1
        if IDENTIFIER_RE.match(token) and toks[index + 1] == "[":
            profile["MemberExpression"] += 1
    profile["Identifier"] = sum(
        1 for token in toks if IDENTIFIER_RE.match(token) and token not in JS_KEYWORDS
    )
    profile["Literal"] = sum(1 for token in toks if NUMBER_RE.match(token))
    return profile


def _syntactic_profile(source: str, language: str) -> Counter:
    if language == "python":
        try:
            return _python_ast_profile(source)
        except SyntaxError:
            return Counter({"PARSE_FAILURE": 1})
    return _javascript_syntactic_profile(source)


def _control_profile(source: str, language: str) -> Counter:
    toks = tokens(source, language)
    controls = (
        ("if", "if"), ("elif", "elif"), ("else", "else"), ("for", "for"),
        ("while", "while"), ("return", "return"), ("try", "try"),
        ("except", "catch"), ("catch", "catch"), ("throw", "throw"),
        ("raise", "throw"), ("break", "break"), ("continue", "continue"),
    )
    counts = Counter()
    for token, bucket in controls:
        counts[bucket] += toks.count(token)
    return counts


def _identifier_style(identifier: str) -> str:
    stripped = identifier.lstrip("_$")
    if not stripped:
        return "empty"
    if identifier.startswith(("_", "$")):
        prefix = "prefixed_"
    else:
        prefix = ""
    if stripped.isupper() and any(c.isalpha() for c in stripped):
        return prefix + "upper"
    if "_" in stripped and stripped.lower() == stripped:
        return prefix + "snake"
    if stripped[0].isupper() and any(c.islower() for c in stripped[1:]):
        return prefix + "upper_camel"
    if any(c.isupper() for c in stripped[1:]) and "_" not in stripped:
        return prefix + "lower_camel"
    if stripped.lower() == stripped:
        return prefix + "lower"
    return prefix + "mixed"


def _style_similarity(left_ids: list[str], right_ids: list[str]) -> float:
    left = Counter(_identifier_style(identifier) for identifier in left_ids)
    right = Counter(_identifier_style(identifier) for identifier in right_ids)
    left_total = sum(left.values())
    right_total = sum(right.values())
    if left_total == 0 and right_total == 0:
        return 1.0
    keys = set(left) | set(right)
    distance = sum(
        abs(left[key] / max(left_total, 1) - right[key] / max(right_total, 1))
        for key in keys
    )
    return max(0.0, 1.0 - distance / 2)


def source_metrics(reference: str, candidate: str, language: str) -> dict[str, float]:
    reference_tokens = tokens(reference, language)
    candidate_tokens = tokens(candidate, language)
    reference_ids = identifiers(reference, language)
    candidate_ids = identifiers(candidate, language)
    return {
        "character_similarity": _sequence_similarity(reference, candidate),
        "token_similarity": _sequence_similarity(reference_tokens, candidate_tokens),
        "identifier_normalized_similarity": _sequence_similarity(
            _normalized_tokens(reference, language),
            _normalized_tokens(candidate, language),
        ),
        "ast_type_similarity": _weighted_jaccard(
            _syntactic_profile(reference, language),
            _syntactic_profile(candidate, language),
        ),
        "control_profile_similarity": _weighted_jaccard(
            _control_profile(reference, language),
            _control_profile(candidate, language),
        ),
        "identifier_multiset_similarity": _weighted_jaccard(
            Counter(reference_ids), Counter(candidate_ids)
        ),
        "identifier_style_similarity": _style_similarity(reference_ids, candidate_ids),
    }


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float:
    positives = [score for label, score in zip(labels, scores) if label == 1]
    negatives = [score for label, score in zip(labels, scores) if label == 0]
    if not positives or not negatives:
        raise ValueError("both classes are required")
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        average = (cursor + 1 + end) / 2
        for position in range(cursor, end):
            ranks[order[position]] = average
        cursor = end
    return ranks


def pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("same nonzero length required")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_ss = sum((x - left_mean) ** 2 for x in left)
    right_ss = sum((y - right_mean) ** 2 for y in right)
    if left_ss == 0 or right_ss == 0:
        return 0.0
    return numerator / math.sqrt(left_ss * right_ss)


def spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return pearson(_ranks(left), _ranks(right))


def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda row: abs(augmented[row][pivot]))
        augmented[pivot], augmented[best] = augmented[best], augmented[pivot]
        if abs(augmented[pivot][pivot]) < 1e-12:
            augmented[pivot][pivot] = 1e-12
        divisor = augmented[pivot][pivot]
        augmented[pivot] = [value / divisor for value in augmented[pivot]]
        for row in range(size):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [
                current - factor * base
                for current, base in zip(augmented[row], augmented[pivot])
            ]
    return [augmented[row][-1] for row in range(size)]


def standardized_linear_model(
    rows: Sequence[dict[str, float]],
    response: str,
    predictors: Sequence[str],
) -> dict[str, float]:
    y_raw = [float(row[response]) for row in rows]
    x_raw = [[float(row[predictor]) for predictor in predictors] for row in rows]

    def standardize(values: list[float]) -> tuple[list[float], float, float]:
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        scale = math.sqrt(variance)
        if scale == 0:
            return [0.0] * len(values), mean, 0.0
        return [(value - mean) / scale for value in values], mean, scale

    y, y_mean, y_scale = standardize(y_raw)
    columns = []
    for index in range(len(predictors)):
        column, _, _ = standardize([row[index] for row in x_raw])
        columns.append(column)

    p = len(predictors)
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for i in range(p):
        for j in range(p):
            xtx[i][j] = sum(columns[i][r] * columns[j][r] for r in range(len(rows)))
        xtx[i][i] += 1e-12
        xty[i] = sum(columns[i][r] * y[r] for r in range(len(rows)))
    beta = _solve_linear(xtx, xty)
    predictions = [
        sum(beta[index] * columns[index][row] for index in range(p))
        for row in range(len(rows))
    ]
    residual_ss = sum((actual - predicted) ** 2 for actual, predicted in zip(y, predictions))
    total_ss = sum(actual**2 for actual in y)
    r2 = 1.0 - residual_ss / total_ss if total_ss else 1.0

    result = {f"beta_{predictor}": coefficient for predictor, coefficient in zip(predictors, beta)}
    result.update({"r_squared": r2, "response_mean": y_mean, "response_scale": y_scale})
    return result


def binomial_cdf(n: int, k: int, probability: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if probability <= 0:
        return 1.0
    if probability >= 1:
        return 0.0 if k < n else 1.0
    return sum(
        comb(n, i) * probability**i * (1 - probability) ** (n - i)
        for i in range(k + 1)
    )


def clopper_pearson(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError((successes, trials))
    alpha = 1.0 - confidence
    if successes == 0:
        lower = 0.0
    else:
        lo, hi = 0.0, 1.0
        target = alpha / 2
        for _ in range(70):
            mid = (lo + hi) / 2
            tail = 1.0 - binomial_cdf(trials, successes - 1, mid)
            if tail < target:
                lo = mid
            else:
                hi = mid
        lower = (lo + hi) / 2

    if successes == trials:
        upper = 1.0
    else:
        lo, hi = 0.0, 1.0
        target = alpha / 2
        for _ in range(70):
            mid = (lo + hi) / 2
            cdf = binomial_cdf(trials, successes, mid)
            if cdf > target:
                lo = mid
            else:
                hi = mid
        upper = (lo + hi) / 2
    return lower, upper


def zero_failure_upper(trials: int, confidence: float = 0.95) -> float:
    gamma = 1.0 - confidence
    return 1.0 - gamma ** (1.0 / trials)


def minimum_zero_failure_trials(target_upper: float, confidence: float = 0.95) -> int:
    gamma = 1.0 - confidence
    return math.floor(math.log(gamma) / math.log(1.0 - target_upper)) + 1
