"""Owned admission controls, not added watermark trials or research observations."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ARTIFACT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTIFACT / "src"))
sys.path.insert(0, str(ARTIFACT))
from covewm.metrics import roc_auc
from check_joint_evidence import feasible_table_comparator
from recheck_extended import roc_auc as reconstruction_auc
from run_all import validate_semantic_evidence
from validate_evidence import rank_auc, run as audit_run


def evidence_fixture():
    """Schema-only owned fixture; zero digests are not measured program evidence."""
    from covewm.tasks import TASKS
    schemes = ("lexical", "structural", "hybrid")
    conditions = ("carrier_only", "format", "rename", "normalize", "random_flip", "strip", "mixed")
    digest = "0" * 64
    parity = [dict(task=t.name, domain_cases=t.domain_size, equal=True,
                   python_hash=digest, javascript_hash=digest) for t in TASKS]
    mutants = [dict(task=t.name, language=lang, mutant_id=i,
                    domain_cases=t.domain_size, source_sha256=digest,
                    parse_ok=True, full_domain_equal=False)
               for t in TASKS for lang in ("python", "javascript") for i in range(1, 4)]
    audits = [dict(task=t.name, language=lang, scheme=scheme, condition=condition,
                   domain_cases=t.domain_size, source_sha256=digest,
                   parse_ok=True, bounded_equivalent=True)
              for t in TASKS for lang in ("python", "javascript")
              for scheme in schemes for condition in conditions]
    return parity, mutants, audits


class EvidenceAdmissionTests(unittest.TestCase):
    def test_auc_requires_complete_pairs(self):
        labels, scores = [1, 1, 0, 0], [.6, .4, .5, .2]
        for implementation in (roc_auc, reconstruction_auc):
            self.assertEqual(implementation(labels, scores), .75)
            with self.subTest(implementation=implementation.__module__), self.assertRaises(ValueError):
                implementation(labels, scores[:-1])

    def test_auc_rejects_nonfinite_or_nonbinary_observations(self):
        for implementation in (roc_auc, reconstruction_auc):
            for labels, scores in (([1, 0], [float("nan"), .5]),
                                   ([1, 0], [float("inf"), .5]),
                                   ([1, 0, 2], [.8, .2, .4]),
                                   ([1, 0, "1"], [.8, .2, .4]),
                                   ([1, 1], [.8, .2])):
                with self.subTest(implementation=implementation.__module__, labels=labels, scores=scores):
                    with self.assertRaises(ValueError):
                        implementation(labels, scores)

    def test_comparator_uses_one_shot_observations(self):
        rows = [(True, True), (True, None), (False, None)]
        self.assertEqual(feasible_table_comparator(iter(rows)), (1, 2))
        self.assertEqual(feasible_table_comparator(iter(rows), (2, 2)), (1, 2))

    def test_comparator_rejects_unadmitted_labels_and_marginals(self):
        for rows, marginal in (([], None), ([(1, None)], None),
                               ([(True, 1)], None), ([(True, None)], (0, 2)),
                               ([(True, None)], (True, 1)),
                               ([(True, None)], (1, 0)),
                               ([(False, False)], (1, 1))):
            with self.subTest(rows=rows, marginal=marginal), self.assertRaises(ValueError):
                feasible_table_comparator(iter(rows), marginal)

    def test_semantic_gate_rejects_duplicate_in_place_of_missing_key(self):
        original = evidence_fixture()
        validate_semantic_evidence(*original)
        for table in range(3):
            rows = copy.deepcopy(original)
            rows[table][-1] = dict(rows[table][0])
            with self.subTest(table=table), self.assertRaises(ValueError):
                validate_semantic_evidence(*rows)

    def test_semantic_gate_checks_domains_and_typed_flags(self):
        original = evidence_fixture()
        for table, field, value in ((0, "domain_cases", 1), (1, "domain_cases", 1),
                                    (2, "domain_cases", 1), (0, "equal", "True"),
                                    (1, "parse_ok", "True"), (2, "bounded_equivalent", "True"),
                                    (0, "javascript_hash", "1" * 64),
                                    (1, "source_sha256", "not-a-digest")):
            rows = copy.deepcopy(original)
            rows[table][0][field] = value
            with self.subTest(table=table, field=field), self.assertRaises(ValueError):
                validate_semantic_evidence(*rows)

    def test_average_rank_baseline_has_same_admission_and_tie_obligations(self):
        for labels, scores, expected in (([1, 0], [.5, .5], .5),
                                         ([1, 0], [.8, .2], 1),
                                         ([1, 0], [.2, .8], 0),
                                         ([1, 1, 0, 0], [.6, .4, .5, .2], .75),
                                         ([1, 0, 1, 0], [.5, .5, .5, .5], .5)):
            self.assertEqual(float(rank_auc(labels, scores)), expected)
            self.assertEqual(roc_auc(labels, scores), expected)
        for labels, scores in (([1, 0], [.5]), ([1, 0], [float("nan"), .5]),
                               ([1, 0, 2], [.8, .2, .4]), ([1, 1], [.8, .2])):
            with self.assertRaises(ValueError):
                rank_auc(labels, scores)

    def test_audit_refuses_existing_or_overlapping_output_before_reading_inputs(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            retained = root / "retained"
            retained.mkdir()
            for out in (retained, retained / "new", root):
                with self.assertRaises(ValueError):
                    audit_run(retained, out)

    def test_default_workflow_includes_reporting_and_joint_audit(self):
        workflow = (ARTIFACT / ".github/workflows/scientific-checks.yml").read_text(encoding="utf-8")
        self.assertIn('discover -s regressions', workflow)
        self.assertIn('validate_evidence.py --results .scientific-output/results --out .scientific-output/evidence-audit', workflow)
        self.assertIn('export COVEWM_RESULTS="$PWD/.scientific-output/results"', workflow)


if __name__ == "__main__":
    unittest.main()
