from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import os
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ARTIFACT = Path(__file__).resolve().parents[1]
RESULTS = Path(os.environ.get("COVEWM_RESULTS", ARTIFACT / "results"))
sys.path.insert(0, str(ARTIFACT / "src"))

from covewm.benchmark import (  # noqa: E402
    PAYLOAD_BITS,
    CarrierState,
    binomial_tail,
    carrier_only_states,
    detector,
    extract_carriers,
    payload_bits,
    render_carriers,
)
from covewm.extended import _tv_extreme, syntax_aware_local_rename  # noqa: E402
from covewm.tasks import TASKS, domain_cases, validate_domains  # noqa: E402
sys.path.insert(0, str(ARTIFACT))
from run_all import validate_semantic_evidence  # noqa: E402
from recheck_extended import local_rename  # noqa: E402


class ArtifactTests(unittest.TestCase):
    def test_detector_one_shot_accounting(self) -> None:
        states = [CarrierState(0, "lexical", 1, 0, True, "bit_flip"),
                  CarrierState(1, "lexical", 1, 1, False, "delete")]
        expected = detector(states)
        self.assertEqual(expected["realized_bit_changes"], 1)
        self.assertEqual(expected["deletions"], 1)
        self.assertEqual(detector(iter(states)), expected)

    def test_unicode_rename_offsets(self) -> None:
        for prefix in ('label = "é";', 'label = "汉字";', 'label = "🙂";',
                       'label = "line\u2028separator";'):
            source = f"def f(x):\n    {prefix} return x + 1\n"
            transformed = syntax_aware_local_rename(source, 1, "x", "renamed")
            self.assertEqual(local_rename(source, 1, "x", "renamed"), transformed)
            namespace = {}
            exec(compile(transformed, "<owned-unicode-test>", "exec"), namespace)
            self.assertEqual(namespace["f"](2), 3)

    def test_semantic_evidence_gates(self) -> None:
        parity = [{"equal": True} for _ in TASKS]
        mutants = [{"parse_ok": True, "full_domain_equal": False}
                   for _ in range(len(TASKS) * 2 * 3)]
        audits = [{"parse_ok": True, "bounded_equivalent": True}
                  for _ in range(len(TASKS) * 2 * 3 * 7)]
        validate_semantic_evidence(parity, mutants, audits)
        for rows, key, bad in ((parity, "equal", False),
                               (mutants, "parse_ok", False),
                               (mutants, "full_domain_equal", True),
                               (audits, "parse_ok", False),
                               (audits, "bounded_equivalent", False)):
            good = rows[0][key]
            rows[0][key] = bad
            with self.assertRaises(ValueError):
                validate_semantic_evidence(parity, mutants, audits)
            rows[0][key] = good

    def test_domain_contract(self) -> None:
        validate_domains()
        self.assertEqual(len(TASKS), 12)
        self.assertEqual(sum(len(domain_cases(task.name)) for task in TASKS), 33013)

    def test_detector_threshold_probability(self) -> None:
        self.assertEqual(PAYLOAD_BITS, 24)
        self.assertAlmostEqual(binomial_tail(24, 22), 1.7940998077392578e-05, places=18)
        self.assertGreater(binomial_tail(24, 21), 1e-4)
        self.assertLessEqual(binomial_tail(24, 22), 1e-4)

    def test_carrier_round_trip(self) -> None:
        for language in ("python", "javascript"):
            for scheme in ("lexical", "structural", "hybrid"):
                bits = payload_bits("leap_year", language, 0)
                states = carrier_only_states(bits, scheme)
                source = render_carriers(language, states)
                self.assertEqual([extract_carriers(source, language)[index] for index in range(PAYLOAD_BITS)], bits)
                result = detector(states)
                self.assertTrue(result["detected"])
                self.assertEqual(result["surviving_sites"], 24)

    def test_scope_aware_local_rename(self) -> None:
        source = "def outer(value):\n    def inner(value):\n        return value + 1\n    return value + inner(2)\n"
        transformed = syntax_aware_local_rename(source, 1, "value", "renamed")
        tree = ast.parse(transformed)
        self.assertIn("renamed", transformed)
        inner = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "inner")
        self.assertEqual(inner.args.args[0].arg, "value")
        namespace: dict[str, object] = {}
        exec(compile(transformed, "<test>", "exec"), namespace)
        self.assertEqual(namespace["outer"](3), 6)  # type: ignore[index,operator]

    def test_total_variation_extremes_and_tie(self) -> None:
        weights = {"a": Fraction(1, 2), "b": Fraction(1, 2)}
        values = {"a": Fraction(3, 4), "b": Fraction(-1, 4)}
        low, witness = _tv_extreme(weights, values, Fraction(1, 4), minimize=True)
        self.assertEqual(low, 0)
        self.assertEqual(witness, {"a": Fraction(1, 4), "b": Fraction(3, 4)})

    def test_transfer_corpus_contract(self) -> None:
        corpus = ARTIFACT / "corpus"
        with (corpus / "transfer_manifest.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 120)
        self.assertEqual(len({row["project"] for row in rows}), 24)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["project"]] = counts.get(row["project"], 0) + 1
            source = (corpus / "transfer" / row["project_slug"] / f"module-{int(row['selection_rank']):02d}.py").read_text(encoding="utf-8")
            self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), row["source_sha256"])
        self.assertTrue(all(value == 5 for value in counts.values()))

    def test_external_protocol_replay_rank_change(self) -> None:
        path = RESULTS / "derived/external_protocol_rankings.csv"
        summary_path = RESULTS / "derived/external_protocol_replay_summary.json"
        if not path.exists() or not summary_path.exists():
            self.skipTest("results not generated")
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        winners = {row["winner"] for row in rows}
        self.assertEqual(winners, {"lexical", "structural", "hybrid"})
        summary = json.loads(summary_path.read_text())
        self.assertEqual(
            summary["stone_stem"]["status"],
            "NOT_COMPUTED_COMPONENT_MISMATCH",
        )

    def test_external_protocol_provenance_contract(self) -> None:
        evidence_dir = ARTIFACT / "external-baselines" / "evidence"
        expected = {
            "sweet-protocol.json": ("SWEET", "853b47eb064c180beebd383302d09491fc98a565"),
            "codeip-protocol.json": ("CodeIP", "5f84062064947a0e2137ebda0bd3a9ae8ceb1736"),
            "srcmarker-protocol.json": ("SrcMarker", "2fb71cf816c12b0b07bb4d84dbe44ca0816662eb"),
            "stone-protocol.json": ("STONE", "bb5d809c0c494a219411e861f2313cca2b9fd7b4"),
        }
        for filename, (system, commit) in expected.items():
            record = json.loads((evidence_dir / filename).read_text(encoding="utf-8"))
            self.assertEqual(record["system"], system)
            self.assertEqual(record["commit"], commit)
            self.assertEqual(record["full_system_execution"], "NO")
            self.assertEqual(record["redistributed_source"], "NO")
            self.assertTrue(record["source_blob_sha"])
            self.assertTrue(record["source_path"])
            self.assertTrue(record["definition_record"]["definition"])

        with (ARTIFACT / "external_resources.csv").open(encoding="utf-8", newline="") as handle:
            resources = list(csv.DictReader(handle))
        protocol_rows = {
            row["name"].split()[0]: row
            for row in resources
            if row["resource_type"] == "public code-watermark evaluation protocol"
        }
        self.assertEqual(len(protocol_rows), 4)
        self.assertTrue(all(row["internals_modified"] == "false" for row in protocol_rows.values()))

    def test_decision_functional_rank_change(self) -> None:
        path = RESULTS / "derived/decision_functional_sensitivity.csv"
        if not path.exists():
            self.skipTest("results not generated")
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        winners = {row["winner"] for row in rows}
        self.assertGreaterEqual(len(winners), 2)

    def test_frozen_summary_when_present(self) -> None:
        summary_path = RESULTS / "summary.json"
        if not summary_path.exists():
            self.skipTest("results not generated")
        summary = json.loads(summary_path.read_text())
        expected = {
            "task_families": 12,
            "domain_cases_per_language": 33013,
            "mutants": 72,
            "ineffective_mutants": 0,
            "nominal_surviving_mutants": 6,
            "semantic_audit_pairs": 504,
            "semantic_audit_failures": 0,
            "metric_intervention_observations": 1296,
            "robustness_observations": 76032,
        }
        for key, value in expected.items():
            self.assertEqual(summary[key], value)
        self.assertTrue(math.isclose(summary["false_positive"]["exact_null_false_positive_probability"], 1.7940998077392578e-05, rel_tol=0, abs_tol=1e-20))


if __name__ == "__main__":
    unittest.main()
