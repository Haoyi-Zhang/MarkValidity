from __future__ import annotations

import math
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any


PROTOCOL_ORDER = (
    "native_exact_tail_detection",
    "srcmarker_bit_accuracy",
    "srcmarker_exact_message",
    "codeip_available_prefix_exact",
    "sweet_exact_null_auroc",
    "sweet_tpr_at_fpr_0_01",
    "sweet_tpr_at_fpr_0_05",
)


def _decimal_z(match_count: int, surviving_sites: int) -> Decimal:
    if surviving_sites <= 0:
        raise ValueError("z score requires at least one observed site")
    with localcontext() as context:
        context.prec = 60
        value = Decimal(2 * match_count - surviving_sites) / Decimal(surviving_sites).sqrt()
        return value.quantize(Decimal("1e-40"))


def _format_fraction(value: Fraction, places: int = 12) -> str:
    with localcontext() as context:
        context.prec = 80
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return f"{decimal_value:.{places}f}"


def _exact_null_discrimination(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay a z-score ROC summary against the exact fair-bit null.

    The public SWEET evaluation reports AUROC and TPR at selected FPR bounds from
    negative and watermarked z-score arrays.  Our benchmark has an analytic null
    rather than a human-code score file.  For every observed number of surviving
    sites, this routine enumerates the corresponding Binomial(n, 1/2) null and
    pools those exact masses with the empirical distribution of n.  Rows with no
    surviving sites have no defined z score and are reported, not silently given
    an arbitrary value.
    """

    valid = [row for row in rows if int(row["surviving_sites"]) > 0]
    omitted = len(rows) - len(valid)
    count = len(valid)
    if count == 0:
        raise ValueError("no rows have an observed site")

    surviving_counts = Counter(int(row["surviving_sites"]) for row in valid)
    null_mass: dict[Decimal, Fraction] = defaultdict(Fraction)
    for surviving_sites, frequency in surviving_counts.items():
        denominator = count * (2 ** surviving_sites)
        for matches in range(surviving_sites + 1):
            null_mass[_decimal_z(matches, surviving_sites)] += Fraction(
                frequency * math.comb(surviving_sites, matches), denominator
            )

    positive_counts = Counter(
        _decimal_z(int(row["match_count"]), int(row["surviving_sites"])) for row in valid
    )
    score_values = sorted(set(null_mass) | set(positive_counts))

    cumulative_below = Fraction(0)
    null_below: dict[Decimal, Fraction] = {}
    for score in score_values:
        null_below[score] = cumulative_below
        cumulative_below += null_mass.get(score, Fraction(0))

    auc = sum(
        Fraction(positive_count, count)
        * (null_below[score] + null_mass.get(score, Fraction(0)) / 2)
        for score, positive_count in positive_counts.items()
    )

    bounds = (Fraction(0), Fraction(1, 100), Fraction(5, 100))
    best_tpr = {bound: Fraction(0) for bound in bounds}
    cumulative_fpr = Fraction(0)
    cumulative_tpr = Fraction(0)
    for score in sorted(score_values, reverse=True):
        cumulative_fpr += null_mass.get(score, Fraction(0))
        cumulative_tpr += Fraction(positive_counts.get(score, 0), count)
        for bound in bounds:
            if cumulative_fpr <= bound and cumulative_tpr > best_tpr[bound]:
                best_tpr[bound] = cumulative_tpr

    return {
        "auc": auc,
        "tpr_at_fpr_0": best_tpr[Fraction(0)],
        "tpr_at_fpr_0_01": best_tpr[Fraction(1, 100)],
        "tpr_at_fpr_0_05": best_tpr[Fraction(5, 100)],
        "included_rows": count,
        "undefined_zero_site_rows": omitted,
        "null_probability_mass": cumulative_below,
    }


def generate_external_protocol_replay(
    robustness_rows: list[dict[str, Any]], output_dir
) -> dict[str, Any]:
    """Apply frozen public evaluation functionals to one common response matrix.

    This is a protocol comparison, not a performance reproduction of the public
    watermark systems.  No external model, checkpoint, generated code, or hidden
    test set is used.  The only input is this benchmark's frozen carrier outcomes.
    """

    from pathlib import Path
    import csv
    import json

    output_dir = Path(output_dir)
    by_scheme: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in robustness_rows:
        by_scheme[str(row["scheme"])].append(row)

    protocol_scores: dict[str, dict[str, Fraction]] = defaultdict(dict)
    protocol_rows: list[dict[str, Any]] = []
    zero_site_rows: dict[str, int] = {}

    for scheme in sorted(by_scheme):
        rows = by_scheme[scheme]
        denominator = len(rows)
        native = Fraction(sum(int(row["detected"]) for row in rows), denominator)
        bit_accuracy = Fraction(
            sum(int(row["match_count"]) for row in rows), denominator * 24
        )
        exact_message = Fraction(
            sum(
                int(row["match_count"]) == 24 and int(row["surviving_sites"]) == 24
                for row in rows
            ),
            denominator,
        )
        # Indexed-survivor agreement inspired by CodeIP, not literal equality
        # with the original contiguous message prefix after interior erasure.
        # Zero-site agreement is vacuously true. Historical output keys remain.
        available_prefix = Fraction(
            sum(
                int(row["match_count"]) == int(row["surviving_sites"])
                for row in rows
            ),
            denominator,
        )
        nonempty_available_prefix = Fraction(
            sum(
                int(row["surviving_sites"]) > 0
                and int(row["match_count"]) == int(row["surviving_sites"])
                for row in rows
            ),
            denominator,
        )
        sweet = _exact_null_discrimination(rows)
        zero_site_rows[scheme] = int(sweet["undefined_zero_site_rows"])

        values = {
            "native_exact_tail_detection": native,
            "srcmarker_bit_accuracy": bit_accuracy,
            "srcmarker_exact_message": exact_message,
            "codeip_available_prefix_exact": available_prefix,
            "sweet_exact_null_auroc": sweet["auc"],
            "sweet_tpr_at_fpr_0_01": sweet["tpr_at_fpr_0_01"],
            "sweet_tpr_at_fpr_0_05": sweet["tpr_at_fpr_0_05"],
        }
        for protocol, value in values.items():
            protocol_scores[protocol][scheme] = value

        protocol_rows.append(
            {
                "scheme": scheme,
                "total_rows": denominator,
                "zero_surviving_site_rows": zero_site_rows[scheme],
                "sweet_defined_rows": sweet["included_rows"],
                **{protocol: _format_fraction(value) for protocol, value in values.items()},
                "codeip_nonempty_prefix_sensitivity": _format_fraction(nonempty_available_prefix),
                "codeip_empty_prefix_contribution": _format_fraction(available_prefix - nonempty_available_prefix),
            }
        )

    ranking_rows: list[dict[str, Any]] = []
    winners: dict[str, str] = {}
    for protocol in PROTOCOL_ORDER:
        ranking = sorted(
            protocol_scores[protocol].items(), key=lambda item: (-item[1], item[0])
        )
        winner = ranking[0][0]
        winners[protocol] = winner
        for rank, (scheme, score) in enumerate(ranking, start=1):
            ranking_rows.append(
                {
                    "protocol": protocol,
                    "scheme": scheme,
                    "score": _format_fraction(score),
                    "rank": rank,
                    "winner": winner,
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "external_protocol_replay.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(protocol_rows[0]))
        writer.writeheader()
        writer.writerows(protocol_rows)
    with (output_dir / "external_protocol_rankings.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ranking_rows[0]))
        writer.writeheader()
        writer.writerows(ranking_rows)

    status = {
        "comparison_unit": "frozen diagnostic carrier outcome",
        "robustness_rows": len(robustness_rows),
        "schemes": sorted(by_scheme),
        "protocols_with_numeric_replay": list(PROTOCOL_ORDER),
        "distinct_numeric_winners": sorted(set(winners.values())),
        "winners": winners,
        "zero_surviving_site_rows": zero_site_rows,
        "stone_stem": {
            "status": "NOT_COMPUTED_COMPONENT_MISMATCH",
            "reason": (
                "The public STEM formula requires human- and watermarked-code "
                "perplexities. This CPU-only diagnostic benchmark has neither an "
                "admissible language-model naturalness measure nor human ratings; "
                "substituting source similarity would change the construct."
            ),
        },
        "scope": (
            "Independent replay of public evaluation functionals on common frozen "
            "outcomes; not an execution or performance comparison of the external "
            "watermark systems."
        ),
    }
    (output_dir / "external_protocol_replay_summary.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return status
