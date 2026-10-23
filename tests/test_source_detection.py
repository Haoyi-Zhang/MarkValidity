"""Owned render/extract bridge; no program or external system is executed."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import check_source_detection as bridge

RESULTS = ROOT / 'results/current/results'


class SourceDetectionTests(unittest.TestCase):
    def test_actual_source_identity_extraction_and_old_semantic_labels(self):
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('program execution forbidden')):
            rows, sources, summary = bridge.analyze(RESULTS)
        self.assertEqual((len(rows), len(sources)), (504, 504))
        self.assertEqual(summary['unique_source_identities'], 408)
        self.assertEqual(summary['distinct_source_identities_in_dense_links'], 384)
        self.assertEqual(summary['dense_source_validity_detection_links'], 432)
        self.assertEqual(summary['positive_linked_decisions'], 122)
        self.assertEqual(summary['other_dense_rows_unmeasured'], 75600)
        self.assertEqual(summary['new_program_executions'], 0)
        self.assertEqual(summary['source_valid_joint_full_universe_lower'], '61/38016')
        self.assertEqual(summary['source_valid_joint_full_universe_upper'], '37861/38016')
        self.assertTrue(all(row['source_identity_matches_retained_audit'] for row in rows))

    def test_changed_source_cannot_inherit_old_semantic_label(self):
        original = bridge.render_program
        with patch.object(bridge, 'render_program', side_effect=lambda *a, **kw: original(*a, **kw) + '\n'):
            with self.assertRaisesRegex(ValueError, 'not the semantically audited source'):
                bridge.analyze(RESULTS)

    def test_state_labels_cannot_replace_source_extraction(self):
        with patch.object(bridge, 'extract_carriers', return_value={99: 1}):
            with self.assertRaisesRegex(ValueError, 'render/extract observation differs'):
                bridge.analyze(RESULTS)

    def test_output_is_fresh_and_does_not_modify_retained_tables(self):
        paths = [RESULTS / name for name in ('results_manifest.csv', 'raw/robustness.csv', 'raw/semantic_audit.csv')]
        before = [p.read_bytes() for p in paths]
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'bridge'
            summary = bridge.run(RESULTS, out)
            self.assertEqual(json.loads((out / 'summary.json').read_text()), summary)
            self.assertEqual(len((out / 'sources.jsonl').read_text().splitlines()), 504)
            self.assertIn('144', (out / 'table.tex').read_text())
            with self.assertRaises(ValueError):
                bridge.run(RESULTS, out)
        self.assertEqual([p.read_bytes() for p in paths], before)


if __name__ == '__main__':
    unittest.main()
