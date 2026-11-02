"""Exercise the shipped duplication receiver with bounded in-memory mutations."""
import unittest
from unittest.mock import patch

import test_reporting_contract as reporting


class DuplicationReceiverContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.witnesses = reporting.rows('duplication_sensitivity.csv')

    def run_receiver(self, witnesses):
        read_rows = reporting.rows

        def changed_rows(name):
            if name == 'duplication_sensitivity.csv':
                return witnesses
            return read_rows(name)

        case = reporting.ReportingContractTests(
            'test_retained_duplication_rows_are_separate_weightings')
        with patch.object(reporting, 'rows', changed_rows):
            case.test_retained_duplication_rows_are_separate_weightings()

    def test_exactly_one_of_each_carrier_accepts_in_any_order(self):
        self.run_receiver(self.witnesses)
        self.run_receiver(list(reversed(self.witnesses)))

    def test_three_lexical_rows_cannot_replace_structural_and_hybrid(self):
        lexical = next(row for row in self.witnesses if row['scheme'] == 'lexical')
        with self.assertRaises(AssertionError):
            self.run_receiver([lexical] * 3)

    def test_missing_duplicate_and_extra_rows_are_rejected(self):
        for index in range(len(self.witnesses)):
            variants = (self.witnesses[:index] + self.witnesses[index + 1:],
                        [self.witnesses[index]] * 3,
                        self.witnesses + [self.witnesses[index]])
            for values in variants:
                with self.subTest(schemes=[row['scheme'] for row in values]):
                    with self.assertRaises(AssertionError):
                        self.run_receiver(values)

    def test_unknown_carrier_is_rejected_as_coverage_failure(self):
        values = [dict(row) for row in self.witnesses]
        values[0]['scheme'] = 'unknown'
        with self.assertRaises(AssertionError):
            self.run_receiver(values)


if __name__ == '__main__':
    unittest.main()
