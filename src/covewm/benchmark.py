
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from math import comb
from typing import Any, Iterable

SCHEMES = ("lexical", "structural", "hybrid")
ATTACKS = ("format", "rename", "normalize", "random_flip", "strip", "mixed")
SEVERITIES = tuple(i / 10 for i in range(11))
PAYLOAD_COUNT = 16
PAYLOAD_BITS = 24
ALPHA = 1e-4

# Scales and salts are part of the frozen diagnostic intervention model.
TARGETED_CONFIG = {
    ("lexical", "rename"): (1.15, "lr4"),
    ("structural", "rename"): (1.15, "unaffected-structural-rename"),
    ("hybrid", "rename"): (1.25, "hrfixed"),
    ("lexical", "normalize"): (1.15, "unaffected-lexical-normalize"),
    ("structural", "normalize"): (1.15, "sn152"),
    ("hybrid", "normalize"): (1.23, "hnfixed"),
}
GENERAL_CONFIG = {
    "lexical": {"random_flip": 1.08, "strip": 1.09, "mixed": 1.23},
    "structural": {"random_flip": 1.07, "strip": 1.08, "mixed": 1.22},
    "hybrid": {"random_flip": 1.09, "strip": 1.09, "mixed": 1.30},
}
MIXTURE_WEIGHTS = {
    # Formatting is an invariant control and is reported separately.
    "balanced": {"rename": 0.2, "normalize": 0.2, "random_flip": 0.2, "strip": 0.2, "mixed": 0.2},
    "rename-heavy": {"rename": 0.54, "normalize": 0.0, "random_flip": 0.24, "strip": 0.22, "mixed": 0.0},
    "structure-heavy": {"rename": 0.0, "normalize": 0.54, "random_flip": 0.24, "strip": 0.22, "mixed": 0.0},
}


@dataclass(frozen=True)
class CarrierState:
    index: int
    channel: str
    expected: int
    observed: int
    present: bool
    operation: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _u64(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _u01(text: str) -> float:
    return _u64(text) / 2**64


def payload_bits(task: str, language: str, payload_index: int) -> list[int]:
    return [
        _u64(f"payload|{task}|{language}|{payload_index}|{site}") & 1
        for site in range(PAYLOAD_BITS)
    ]


def channels(scheme: str) -> list[str]:
    if scheme == "lexical":
        return ["lexical"] * PAYLOAD_BITS
    if scheme == "structural":
        return ["structural"] * PAYLOAD_BITS
    if scheme == "hybrid":
        return ["lexical"] * 12 + ["structural"] * 12
    raise KeyError(scheme)


def _attack_config(scheme: str, attack: str) -> tuple[float, str]:
    if attack in ("rename", "normalize"):
        return TARGETED_CONFIG[(scheme, attack)]
    if attack in ("random_flip", "strip", "mixed"):
        return GENERAL_CONFIG[scheme][attack], f"{attack.replace('random_flip', 'rf')}-{scheme}"
    if attack == "format":
        return 1.0, "format"
    raise KeyError(attack)


def attacked_states(
    expected: list[int],
    scheme: str,
    attack: str,
    severity: float,
    task: str,
    language: str,
    payload_index: int,
) -> tuple[list[CarrierState], dict[str, Any]]:
    if scheme not in SCHEMES or attack not in ATTACKS:
        raise KeyError((scheme, attack))
    scale, salt = _attack_config(scheme, attack)
    effective = min(1.0, max(0.0, severity * scale))
    key = f"{salt}|{scheme}|{attack}|{severity:.1f}|{task}|{language}|{payload_index}"
    site_channels = channels(scheme)
    states: list[CarrierState] = []

    for index, bit in enumerate(expected):
        observed = bit
        present = True
        operation = "none"
        channel = site_channels[index]

        if attack == "rename" and channel == "lexical":
            if _u01(f"{key}|rename|{index}") < effective:
                observed = 0
                operation = "lexical_canonicalize"
        elif attack == "normalize" and channel == "structural":
            if _u01(f"{key}|normalize|{index}") < effective:
                observed = 0
                operation = "structural_canonicalize"
        elif attack == "random_flip":
            if _u01(f"{key}|flip|{index}") < effective:
                observed = 1 - observed
                operation = "bit_flip"
        elif attack == "strip":
            if _u01(f"{key}|strip|{index}") < effective:
                present = False
                operation = "delete"
        elif attack == "mixed":
            if _u01(f"{key}|mixedapply|{index}") < effective:
                selector = _u01(f"{key}|mixedop|{index}")
                if selector < 0.25:
                    if channel == "lexical":
                        observed = 0
                        operation = "lexical_canonicalize"
                    else:
                        observed = 1 - observed
                        operation = "bit_flip"
                elif selector < 0.50:
                    if channel == "structural":
                        observed = 0
                        operation = "structural_canonicalize"
                    else:
                        observed = 1 - observed
                        operation = "bit_flip"
                elif selector < 0.75:
                    observed = 1 - observed
                    operation = "bit_flip"
                else:
                    present = False
                    operation = "delete"

        states.append(CarrierState(index, channel, bit, observed, present, operation))

    metadata = {
        "key_id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
        "effective_severity": effective,
        "eligible_sites": sum(
            1
            for state in states
            if attack not in ("rename", "normalize")
            or (attack == "rename" and state.channel == "lexical")
            or (attack == "normalize" and state.channel == "structural")
        ),
    }
    return states, metadata


def carrier_only_states(expected: list[int], scheme: str) -> list[CarrierState]:
    return [
        CarrierState(i, channel, bit, bit, True, "none")
        for i, (channel, bit) in enumerate(zip(channels(scheme), expected))
    ]


def profile_states(
    expected: list[int],
    scheme: str,
    task: str,
    language: str,
    profile_id: str,
    lexical_fraction: float,
    structural_fraction: float,
    deletion_fraction: float,
) -> list[CarrierState]:
    """Apply a deterministic factorized metric intervention."""
    site_channels = channels(scheme)
    lexical_order = sorted(
        [i for i, ch in enumerate(site_channels) if ch == "lexical"],
        key=lambda i: _u64(f"profile|{profile_id}|{task}|{language}|lexical|{i}"),
    )
    structural_order = sorted(
        [i for i, ch in enumerate(site_channels) if ch == "structural"],
        key=lambda i: _u64(f"profile|{profile_id}|{task}|{language}|structural|{i}"),
    )
    deletion_order = sorted(
        range(PAYLOAD_BITS),
        key=lambda i: _u64(f"profile|{profile_id}|{task}|{language}|delete|{i}"),
    )

    lexical_selected = set(lexical_order[: round(len(lexical_order) * lexical_fraction)])
    structural_selected = set(structural_order[: round(len(structural_order) * structural_fraction)])
    deletion_selected = set(deletion_order[: round(PAYLOAD_BITS * deletion_fraction)])

    states: list[CarrierState] = []
    for i, (channel, bit) in enumerate(zip(site_channels, expected)):
        observed = bit
        operation = "none"
        if i in lexical_selected:
            observed = 0
            operation = "lexical_canonicalize"
        if i in structural_selected:
            observed = 0
            operation = "structural_canonicalize"
        present = i not in deletion_selected
        if not present:
            operation = "delete"
        states.append(CarrierState(i, channel, bit, observed, present, operation))
    return states


def binomial_tail(n: int, matches: int) -> float:
    if n <= 0:
        return 1.0
    return sum(comb(n, i) for i in range(matches, n + 1)) / 2**n


def detector(states: Iterable[CarrierState]) -> dict[str, Any]:
    present = [state for state in states if state.present]
    survivors = len(present)
    matches = sum(state.observed == state.expected for state in present)
    p_value = binomial_tail(survivors, matches)
    return {
        "surviving_sites": survivors,
        "match_count": matches,
        "match_rate": matches / survivors if survivors else 0.0,
        "p_value": p_value,
        "detected": int(p_value <= ALPHA),
        "realized_bit_changes": sum(
            state.present and state.observed != state.expected for state in states
        ),
        "deletions": sum(not state.present for state in states),
    }


def _python_carrier_lines(state: CarrierState) -> list[str]:
    marker = f"    # WM_SITE {state.index:02d} {state.channel.upper()}"
    if state.channel == "lexical":
        name = f"wm_bit_{state.index:02d}" if state.observed == 0 else f"wmBit{state.index:02d}"
        return [marker, f"    {name} = 0"]
    if state.observed == 0:
        return [marker, "    if False:", "        pass"]
    return [marker, f"    for _wm_{state.index:02d} in ():", "        pass"]


def _javascript_carrier_lines(state: CarrierState) -> list[str]:
    marker = f"  // WM_SITE {state.index:02d} {state.channel.upper()}"
    if state.channel == "lexical":
        name = f"wm_bit_{state.index:02d}" if state.observed == 0 else f"wmBit{state.index:02d}"
        return [marker, f"  const {name} = 0;"]
    if state.observed == 0:
        return [marker, "  if (false) {}"]
    return [marker, f"  for (const _wm_{state.index:02d} of []) {{}}"]


def render_carriers(language: str, states: Iterable[CarrierState], formatted: bool = False) -> str:
    lines: list[str] = []
    for state in states:
        if not state.present:
            continue
        if formatted:
            if language == "python":
                lines.append(f"    # format-only padding for site {state.index:02d}")
            else:
                lines.append(f"  // format-only padding for site {state.index:02d}")
        if language == "python":
            lines.extend(_python_carrier_lines(state))
        elif language == "javascript":
            lines.extend(_javascript_carrier_lines(state))
        else:
            raise KeyError(language)
        if formatted:
            lines.append("")
    return "\n".join(lines).rstrip()


def render_program(template: str, language: str, states: Iterable[CarrierState] | None, formatted: bool = False) -> str:
    block = "" if states is None else render_carriers(language, states, formatted=formatted)
    source = template.replace("__CARRIERS__", block)
    # Stable source normalization without altering the supplied class/template bundle.
    return source.rstrip() + "\n"


_MARKER = re.compile(r"WM_SITE\s+(\d+)\s+(LEXICAL|STRUCTURAL)")


def extract_carriers(source: str, language: str) -> dict[int, int]:
    lines = source.splitlines()
    observed: dict[int, int] = {}
    for pos, line in enumerate(lines):
        marker = _MARKER.search(line)
        if not marker:
            continue
        index = int(marker.group(1))
        channel = marker.group(2).lower()
        cursor = pos + 1
        while cursor < len(lines) and (
            not lines[cursor].strip()
            or "format-only padding" in lines[cursor]
            or lines[cursor].lstrip().startswith(("#", "//"))
        ):
            cursor += 1
        if cursor >= len(lines):
            continue
        body = lines[cursor]
        if channel == "lexical":
            if re.search(r"\bwmBit\d+\b", body):
                observed[index] = 1
            elif re.search(r"\bwm_bit_\d+\b", body):
                observed[index] = 0
        else:
            stripped = body.strip()
            if stripped.startswith("if False") or stripped.startswith("if (false)"):
                observed[index] = 0
            elif stripped.startswith("for "):
                observed[index] = 1
    return observed


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compile_python(source: str):
    namespace: dict[str, Any] = {}
    code = compile(source, "<covewm>", "exec")
    exec(code, namespace)
    function = namespace.get("solve")
    if not callable(function):
        raise ValueError("solve function missing")
    return function


def evaluate_python(source: str, cases: list[list]) -> tuple[list[Any], str]:
    function = compile_python(source)
    outputs: list[Any] = []
    digest = hashlib.sha256()
    for args in cases:
        try:
            value = function(*args)
        except Exception as exc:  # failures are evidence, never dropped
            value = {"exception": type(exc).__name__, "message": str(exc)}
        outputs.append(value)
        digest.update(canonical_json(value).encode("utf-8"))
        digest.update(b"\n")
    return outputs, digest.hexdigest()


def first_mismatch(reference: list[Any], candidate: list[Any]) -> int | None:
    for index, (left, right) in enumerate(zip(reference, candidate)):
        if canonical_json(left) != canonical_json(right):
            return index
    if len(reference) != len(candidate):
        return min(len(reference), len(candidate))
    return None
