"""Bounded reporting checks; no scientific runner or archived code is executed."""
import csv
from decimal import Decimal
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / 'results/current/results/derived'
PAPER = ROOT.parent / 'paper'


def rows(name):
    with (DERIVED / name).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


class ReportingContractTests(unittest.TestCase):
    def test_protocol_names_state_unit_and_survivor_rule(self):
        protocol = json.loads((ROOT / 'protocol.json').read_text(encoding='utf-8'))
        robustness = protocol['constructs']['attack_conditioned_robustness']
        self.assertEqual(robustness['unit'], 'one indexed carrier-state configuration')
        self.assertIn('do not assert per-row source extraction', robustness['scope'])
        replay = protocol['external_protocol_replay']
        self.assertIn('CodeIP-inspired indexed-survivor agreement',
                      replay['numeric_functionals'])
        self.assertIn('original indexed target', replay['edge_policies']['CodeIP'])
        self.assertIn('zero survivors are accepted vacuously',
                      replay['edge_policies']['CodeIP'])

    def test_retained_duplication_rows_are_separate_weightings(self):
        family = {(r['scheme'], r['attack']): Decimal(r['mean_detection_rate'])
                  for r in rows('attack_family_means.csv')}
        favored = {'lexical': 'normalize', 'structural': 'rename', 'hybrid': 'strip'}
        witnesses = rows('duplication_sensitivity.csv')
        self.assertEqual(len(witnesses), 3)
        for row in witnesses:
            scheme = row['scheme']
            self.assertEqual(row['favored_attack'], favored[scheme])
            self.assertEqual(int(row['copies_total']), 20)
            macro = Decimal(row['base_equal_stratum_macro'])
            expected = (5 * macro + 19 * family[(scheme, favored[scheme])]) / 24
            self.assertLess(abs(expected - Decimal(row['duplicated_row_micro'])),
                            Decimal('0.000000000002'))
            self.assertEqual(macro, Decimal(row['macro_after_duplication']))
        manuscript = (PAPER / 'main.tex').read_text(encoding='utf-8')
        self.assertIn('separate weightings rather than a common cross-carrier comparison',
                      manuscript)
        self.assertIn('results/current/results/derived/duplication_sensitivity.csv',
                      manuscript)

    def test_legacy_rank_is_display_position_and_threshold_scores_tie(self):
        values = rows('decision_functional_sensitivity.csv')
        self.assertEqual(len(values), 15)
        for functional in {r['functional'] for r in values}:
            group = [r for r in values if r['functional'] == functional]
            ordered = sorted(group, key=lambda r: (-Decimal(r['score']), r['scheme']))
            self.assertEqual([int(r['rank']) for r in ordered], [1, 2, 3])
        threshold = {r['scheme']: r for r in values
                     if r['functional'] == 'share of families at or above 0.30'}
        self.assertEqual(Decimal(threshold['lexical']['score']), Decimal('0.4'))
        self.assertEqual(Decimal(threshold['structural']['score']), Decimal('0.4'))
        self.assertEqual(Decimal(threshold['hybrid']['score']), Decimal('0.6'))
        supplement = (PAPER / 'online-supplement.tex').read_text(encoding='utf-8')
        self.assertIn('Score & Display order & Winner', supplement)
        self.assertIn('not a strict preference rank', supplement)


if __name__ == '__main__':
    unittest.main()
