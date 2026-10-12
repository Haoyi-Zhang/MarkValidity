"""Finite evidence bounds, not watermark generation or attack evaluation.

Each row has an observed binary decision and a validity label that is either
observed or unknown. Unknown is never silently counted as valid or invalid.
The interval is sharp over label completions, not a confidence interval or a
claim that every completion is realizable by an executable program.
"""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class JointBounds:
    trials: int
    decision_positive: int
    known_valid_positive: int
    known_invalid_positive: int
    known_valid_negative: int
    known_invalid_negative: int
    unknown_positive: int
    unknown_negative: int
    valid_total_lower: int
    valid_total_upper: int
    joint_lower: int
    joint_upper: int
    # Analytical completion counts, never reported as measured trials.
    lower_completion: tuple[int, int]
    upper_completion: tuple[int, int]


def joint_bounds(
    observations: Iterable[tuple[bool, bool | None]],
    valid_total: tuple[int, int] | None = None,
) -> JointBounds:
    """Return exact count bounds, optionally with a same-universe marginal.

    If a,c are known valid rows with positive/negative decisions, and u1,u0
    are unknown rows in those groups, then a+x is the joint success count.
    Feasibility requires 0<=x<=u1, 0<=y<=u0, L<=a+c+x+y<=U.
    Eliminating y gives max(0,L-a-c-u0)<=x<=min(u1,U-a-c).
    """
    counts = {(decision, validity): 0 for decision in (False, True)
              for validity in (False, True, None)}
    for decision, validity in observations:
        if type(decision) is not bool or (validity is not None and type(validity) is not bool):
            raise ValueError("decision and known validity must be actual booleans")
        counts[(decision, validity)] += 1
    n = sum(counts.values())
    if not n:
        raise ValueError("empty evidence universe")
    a, b = counts[(True, True)], counts[(True, False)]
    c, d = counts[(False, True)], counts[(False, False)]
    u1, u0 = counts[(True, None)], counts[(False, None)]
    known = a + c
    if valid_total is None:
        lower, upper = known, known + u1 + u0
    else:
        lower, upper = valid_total
        if type(lower) is not int or type(upper) is not int or not 0 <= lower <= upper <= n:
            raise ValueError("invalid validity-count marginal")
        lower, upper = max(lower, known), min(upper, known + u1 + u0)
        if lower > upper:
            raise ValueError("marginal contradicts linked evidence")
    x_low = max(0, lower - known - u0)
    x_high = min(u1, upper - known)
    y_low = max(0, lower - known - x_low)
    y_high = max(0, lower - known - x_high)
    return JointBounds(n, a + b + u1, a, b, c, d, u1, u0,
                       lower, upper, a + x_low, a + x_high,
                       (x_low, y_low), (x_high, y_high))
