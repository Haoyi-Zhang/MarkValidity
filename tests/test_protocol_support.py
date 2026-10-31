import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from covewm.external_replay import support_matched_discrimination


def row(scheme, key, n, m):
    return dict(scheme=scheme, task='owned', language='python', attack='strip',
                severity=str(key), payload_index='0', surviving_sites=n, match_count=m)


class ProtocolSupportTests(unittest.TestCase):
    def test_common_support_and_identical_null_control(self):
        rows = [row(s, 0, 2, 2) for s in ('lexical', 'structural', 'hybrid')]
        rows += [row(s, 1, n, n) for s, n in zip(('lexical', 'structural', 'hybrid'), (0, 1, 2))]
        rows += [row(s, 2, n, n) for s, n in zip(('lexical', 'structural', 'hybrid'), (1, 2, 2))]
        result = support_matched_discrimination(rows)['supports']
        self.assertEqual(result['paired_nonempty']['configurations_per_carrier'], 2)
        equal = result['paired_equal_survivors']
        self.assertEqual(equal['configurations_per_carrier'], 1)
        self.assertTrue(equal['identical_negative_mixtures'])
        self.assertEqual({x['auc'] for x in equal['scores'].values()}, {'0.875000000000'})

    def test_missing_duplicate_and_bad_counts_refused(self):
        rows = [row(s, 0, 2, 2) for s in ('lexical', 'structural', 'hybrid')]
        for bad in (rows[:-1], rows + rows[:1], [dict(rows[0], match_count=3)] + rows[1:],
                    [dict(rows[0], surviving_sites=2.5)] + rows[1:]):
            with self.assertRaises(ValueError):
                support_matched_discrimination(bad)

    def test_no_common_nonempty_rows_is_undefined_not_zero(self):
        rows = [row(s, 0, n, n) for s, n in zip(('lexical', 'structural', 'hybrid'), (0, 1, 2))]
        result = support_matched_discrimination(rows)['supports']
        self.assertEqual(result['paired_nonempty']['status'], 'UNDEFINED_EMPTY_COMMON_SUPPORT')
        self.assertNotIn('scores', result['paired_nonempty'])


if __name__ == '__main__':
    unittest.main()
