"""Reviewed benign boolean tables; no source transformation is executed."""
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from covewm.joint_bounds import joint_bounds
from check_joint_evidence import feasible_table_comparator, indexed, boolean


def exhaustive_completion(observations, marginal):
    unknown = [i for i, (_, v) in enumerate(observations) if v is None]
    outcomes = []
    for values in itertools.product((False, True), repeat=len(unknown)):
        labels = [v for _, v in observations]
        for i, value in zip(unknown, values):
            labels[i] = value
        if marginal[0] <= sum(labels) <= marginal[1]:
            outcomes.append(sum(d and v for (d, _), v in zip(observations, labels)))
    return (min(outcomes), max(outcomes)) if outcomes else None


class JointBoundsTests(unittest.TestCase):
    def test_all_partial_binary_tables_through_four_rows(self):
        alphabet = tuple(itertools.product((False, True), (False, True, None)))
        for n in range(1, 5):
            for observations in itertools.product(alphabet, repeat=n):
                for lower in range(n + 1):
                    for upper in range(lower, n + 1):
                        marginal = lower, upper
                        expected = exhaustive_completion(observations, marginal)
                        if expected is None:
                            with self.assertRaises(ValueError):
                                joint_bounds(observations, marginal)
                            with self.assertRaises(ValueError):
                                feasible_table_comparator(observations, marginal)
                            continue
                        result = joint_bounds(iter(observations), marginal)
                        self.assertEqual((result.joint_lower, result.joint_upper), expected)
                        self.assertEqual(feasible_table_comparator(observations, marginal), expected)
                        known = result.known_valid_positive + result.known_valid_negative
                        for x, y in (result.lower_completion, result.upper_completion):
                            self.assertTrue(0 <= x <= result.unknown_positive)
                            self.assertTrue(0 <= y <= result.unknown_negative)
                            self.assertTrue(lower <= known + x + y <= upper)

    def test_same_marginals_do_not_identify_joint_success(self):
        rows = [(True, None)] * 5 + [(False, None)] * 5
        result = joint_bounds(rows, (5, 5))
        self.assertEqual((result.joint_lower, result.joint_upper), (0, 5))

    def test_linked_evidence_tightens_and_full_evidence_collapses(self):
        rows = [(True, True), (True, False), (True, None), (False, True)]
        partial = joint_bounds(rows)
        self.assertEqual((partial.joint_lower, partial.joint_upper), (1, 2))
        complete = joint_bounds([(d, False if v is None else v) for d, v in rows])
        self.assertEqual((complete.joint_lower, complete.joint_upper), (1, 1))

    def test_rejects_ambiguous_flags_counts_and_duplicate_coverage(self):
        for rows in ([], [(1, True)], [(True, "False")], [(True, 0)]):
            with self.assertRaises(ValueError):
                joint_bounds(rows)
        for marginal in ((-1, 1), (0, 2), (1, 0), (False, 1)):
            with self.assertRaises(ValueError):
                joint_bounds([(True, True)], marginal)
        with self.assertRaises(ValueError):
            boolean("unknown")
        with self.assertRaises(ValueError):
            indexed([{"id": "a"}, {"id": "a"}], lambda r: r["id"], {"a"})
        with self.assertRaises(ValueError):
            indexed([{"id": "b"}], lambda r: r["id"], {"a"})


if __name__ == "__main__":
    unittest.main()
