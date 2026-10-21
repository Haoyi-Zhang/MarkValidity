"""Bounded numeric contracts; no sampling or scientific trials are generated."""
from decimal import Decimal, localcontext
from functools import lru_cache
from math import comb, isfinite
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from covewm.metrics import binomial_cdf, clopper_pearson


def decimal_cdf(n, k, probability):
    """Independent high-precision recurrence from P(X=0), not a modal sum."""
    if k < 0:
        return Decimal(0)
    if k >= n or probability == 0:
        return Decimal(1)
    if probability == 1:
        return Decimal(0)
    term = (1 - probability) ** n
    total = term
    for i in range(k):
        term *= Decimal(n - i) / Decimal(i + 1) * probability / (1 - probability)
        total += term
    return total


@lru_cache(maxsize=None)
def decimal_interval(successes, trials, confidence="0.95"):
    with localcontext() as context:
        context.prec = 70
        alpha = 1 - Decimal(confidence)
        def inverse(k, target):
            lo, hi = Decimal(0), Decimal(1)
            for _ in range(95):
                mid = (lo + hi) / 2
                if decimal_cdf(trials, k, mid) > target:
                    lo = mid
                else:
                    hi = mid
            return float((lo + hi) / 2)
        return (0.0 if successes == 0 else inverse(successes - 1, 1 - alpha / 2),
                1.0 if successes == trials else inverse(successes, alpha / 2))


class BinomialIntervalTests(unittest.TestCase):
    def assert_interval(self, k, n, confidence=0.95):
        got = clopper_pearson(k, n, confidence)
        expected = decimal_interval(k, n, str(confidence))
        for actual, reference in zip(got, expected):
            self.assertTrue(isfinite(actual))
            self.assertAlmostEqual(actual, reference, delta=2e-13)
        self.assertLessEqual(got[0], k / n)
        self.assertLessEqual(k / n, got[1])

    def test_balanced_two_thousand(self):
        self.assert_interval(1000, 2000)

    def test_balanced_three_thousand(self):
        self.assert_interval(1500, 3000)

    def test_nondefault_confidence(self):
        self.assert_interval(1000, 2000, 0.8)
        self.assert_interval(3, 120, 0.99)

    def test_current_response_and_transfer_controls(self):
        for k, n in ((190, 384), (192, 384), (3, 120), (120, 120)):
            with self.subTest(k=k, n=n):
                self.assert_interval(k, n)

    def test_current_sparse_large_controls(self):
        self.assert_interval(48, 2_000_000)
        self.assert_interval(1, 30_000)

    def test_interval_symmetry(self):
        for k, n in ((0, 2000), (1, 2000), (731, 2000), (48, 2_000_000)):
            with self.subTest(k=k, n=n):
                left = clopper_pearson(k, n)
                right = clopper_pearson(n - k, n)
                self.assertAlmostEqual(left[0], 1 - right[1], delta=2e-13)
                self.assertAlmostEqual(left[1], 1 - right[0], delta=2e-13)

    def test_exact_count_endpoints(self):
        for n in (1, 120, 384, 2000):
            with localcontext() as context:
                context.prec = 70
                root = Decimal("0.025") ** (Decimal(1) / n)
                zero, all_success = clopper_pearson(0, n), clopper_pearson(n, n)
                self.assertEqual(zero[0], 0.0)
                self.assertEqual(all_success[1], 1.0)
                self.assertAlmostEqual(zero[1], float(1 - root), delta=2e-13)
                self.assertAlmostEqual(all_success[0], float(root), delta=2e-13)

    def test_cdf_matches_direct_decimal_sum(self):
        with localcontext() as context:
            context.prec = 70
            for n in (0, 1, 8, 24, 64):
                for p in (Decimal("0.001"), Decimal("0.125"), Decimal("0.5"),
                          Decimal("0.875"), Decimal("0.999")):
                    for k in range(-1, n + 1):
                        if k < 0:
                            expected = Decimal(0)
                        else:
                            expected = sum(Decimal(comb(n, i)) * p ** i * (1 - p) ** (n - i)
                                           for i in range(k + 1))
                        self.assertAlmostEqual(binomial_cdf(n, k, float(p)), float(expected), delta=2e-14)

    def test_moderate_cdf_and_small_tail(self):
        with localcontext() as context:
            context.prec = 80
            for k, p in ((1000, "0.5"), (700, "0.5"), (0, "0.001")):
                expected = float(decimal_cdf(2000, k, Decimal(p)))
                actual = binomial_cdf(2000, k, float(p))
                self.assertGreater(actual, 0)
                self.assertAlmostEqual(actual / expected, 1, delta=2e-12)

    def test_cdf_support_and_probability_endpoints(self):
        self.assertEqual(binomial_cdf(5, -1, .4), 0)
        self.assertEqual(binomial_cdf(5, 5, .4), 1)
        self.assertEqual(binomial_cdf(5, 0, 0), 1)
        self.assertEqual(binomial_cdf(5, 4, 1), 0)
        self.assertEqual(binomial_cdf(0, 0, .5), 1)

    def test_malformed_interval_inputs(self):
        for k, n in ((-1, 2), (3, 2), (0, 0), (0, -1), (True, 2),
                     (0, True), (1.5, 2), (1, 2.5), ("1", 2), (0, None)):
            with self.subTest(k=k, n=n), self.assertRaises(ValueError):
                clopper_pearson(k, n)
        for confidence in (0, 1, 10 ** 400, -.1, 1.1, float("nan"), float("inf"),
                           -float("inf"), True, None, "0.95"):
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                clopper_pearson(1, 2, confidence)

    def test_malformed_cdf_inputs(self):
        for n, k in ((-1, 0), (True, 0), (3, True), (2.5, 1), (3, 1.5), (None, 0)):
            with self.subTest(n=n, k=k), self.assertRaises(ValueError):
                binomial_cdf(n, k, .5)
        for probability in (-.1, 1.1, 10 ** 400, float("nan"), float("inf"), True, None, ".5"):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                binomial_cdf(3, 1, probability)


if __name__ == "__main__":
    unittest.main()
