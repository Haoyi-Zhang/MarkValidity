"""Data-only receiving regressions; no task, compiler or model execution."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'src'))
import validate_evidence as audit
import check_protocol_support as support
from run_all import validate_semantic_evidence
from covewm.external_replay import generate_external_protocol_replay, support_matched_discrimination


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


class ReceivingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = ROOT/'results/current/results'
        cls.semantic = []
        for name, flags in (('cross_language_parity', ('equal',)),
                            ('mutants', ('parse_ok', 'full_domain_equal')),
                            ('semantic_audit', ('parse_ok', 'bounded_equivalent'))):
            rows = read(cls.results/'raw'/f'{name}.csv')
            for row in rows:
                row['domain_cases'] = int(row['domain_cases'])
                for flag in flags:
                    row[flag] = audit.boolean(row[flag])
                if 'mutant_id' in row:
                    row['mutant_id'] = int(row['mutant_id'])
            cls.semantic.append(rows)

    def test_one_shot_iterables_receive_every_semantic_check(self):
        validate_semantic_evidence(*(iter(rows) for rows in self.semantic))
        for group, field, value in ((0, 'domain_cases', -1), (0, 'equal', 1),
                                    (1, 'parse_ok', 'True'), (2, 'bounded_equivalent', 1)):
            for iterator in (False, True):
                rows = copy.deepcopy(self.semantic)
                rows[group][0][field] = value
                with self.subTest(group=group, field=field, iterator=iterator), self.assertRaises(ValueError):
                    validate_semantic_evidence(*(iter(r) if iterator else r for r in rows))
        for iterator in (False, True):
            rows = copy.deepcopy(self.semantic); rows[1][-1] = rows[1][0]
            with self.assertRaises(ValueError):
                validate_semantic_evidence(*(iter(r) if iterator else r for r in rows))

    def test_fixed_diagnostic_fields_cannot_shrink_with_input(self):
        rows = read(self.results/'raw/diagnostic_pairs.csv')
        audit.require_fields(rows, audit.DIAGNOSTIC_FIELDS, 'diagnostic')
        for metric in audit.SIMILARITY_METRICS:
            for rename in (False, True):
                bad = copy.deepcopy(rows)
                for row in bad:
                    old = row.pop(metric)
                    if rename: row['replacement_similarity'] = old
                with self.subTest(metric=metric, rename=rename), self.assertRaises(ValueError):
                    audit.require_fields(bad, audit.DIAGNOSTIC_FIELDS, 'diagnostic')

    def test_dropped_metric_and_matching_auc_rows_reject_despite_new_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp)/'results'; results.mkdir()
            manifest = read(self.results/'results_manifest.csv')
            names = ('raw/cross_language_parity.csv', 'raw/mutants.csv', 'raw/semantic_audit.csv',
                     'raw/diagnostic_pairs.csv', 'derived/semantic_proxy_auc.csv',
                     'derived/contextual_semantic_proxy_auc.csv')
            for name in names:
                path = results/name; path.parent.mkdir(parents=True, exist_ok=True)
                rows = read(self.results/name)
                if name.endswith('diagnostic_pairs.csv'):
                    for row in rows: row.pop('character_similarity')
                elif name.startswith('derived/'):
                    rows = [r for r in rows if r['indicator'] != 'character_similarity']
                write(path, rows)
            for row in manifest:
                path = results/row['relative_path']
                if path.exists():
                    data = path.read_bytes(); row.update(sha256=hashlib.sha256(data).hexdigest(), bytes=str(len(data)))
            write(results/'results_manifest.csv', manifest)
            with self.assertRaisesRegex(ValueError, 'diagnostic exact field inventory'):
                audit.retained_analysis(results, Path(tmp)/'out')

    def test_detector_counts_and_decisions_are_typed_and_consistent(self):
        valid = dict(scheme='lexical', task='owned', language='python', attack='format',
                     severity='0.0', payload_index='0', surviving_sites=24, match_count=24, detected=1)
        mutations = [('surviving_sites', 24.9), ('match_count', 23.9), ('surviving_sites', True),
                     ('match_count', '24.0'), ('match_count', -1), ('match_count', 25),
                     ('detected', 2), ('detected', True), ('detected', 0), ('detected', '1.0')]
        for field, value in mutations:
            bad = dict(valid, **{field: value})
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)/'out'
                with self.assertRaises(ValueError): generate_external_protocol_replay([bad], out)
                self.assertFalse(out.exists())
                paired = [dict(bad, scheme=s) for s in ('lexical', 'structural', 'hybrid')]
                with self.assertRaises(ValueError): support_matched_discrimination(paired)
        with tempfile.TemporaryDirectory() as tmp:
            a = generate_external_protocol_replay([valid], Path(tmp)/'typed')
            b = generate_external_protocol_replay([{k:str(v) if type(v) is int else v for k,v in valid.items()}], Path(tmp)/'csv')
            self.assertEqual(a, b)
            self.assertEqual((Path(tmp)/'typed/external_protocol_replay.csv').read_bytes(),
                             (Path(tmp)/'csv/external_protocol_replay.csv').read_bytes())

    def test_frozen_cli_rejects_subset_even_when_manifest_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp)/'results'; (results/'raw').mkdir(parents=True)
            all_rows = read(self.results/'raw/robustness.csv')
            sample = [next(r for r in all_rows if r['scheme'] == scheme) for scheme in ('lexical','structural','hybrid')]
            write(results/'raw/robustness.csv', sample)
            data = (results/'raw/robustness.csv').read_bytes()
            write(results/'results_manifest.csv', [dict(relative_path='raw/robustness.csv',
                  sha256=hashlib.sha256(data).hexdigest(), bytes=str(len(data)))])
            for optimized in (False, True):
                out = Path(tmp)/('optimized' if optimized else 'ordinary')
                command = [sys.executable, '-X', 'utf8'] + (['-O'] if optimized else []) + ['-B', str(ROOT/'check_protocol_support.py'),
                    '--results', str(results), '--out', str(out)]
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('exact key coverage mismatch', result.stderr)
                self.assertFalse(out.exists())
            for mutation in ('missing', 'wrong-key'):
                rows = all_rows[:-1] if mutation == 'missing' else [dict(all_rows[0], task='unregistered')] + all_rows[1:]
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    support.indexed(rows, support.key, support.expected_keys(), 'frozen support matrix')

    def test_retained_data_analysis_keeps_all_296_comparisons(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(subprocess, 'Popen', side_effect=AssertionError('no native execution')):
            result = audit.retained_analysis(self.results, Path(tmp))
        self.assertEqual((result['diagnostic_pairs'], result['auc_comparisons']), (576, 296))

    def test_retained_replay_numbers_and_full_support_are_unchanged(self):
        rows = read(self.results/'raw/robustness.csv')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'replay'
            generate_external_protocol_replay(rows, out)
            for name in ('external_protocol_replay.csv', 'external_protocol_rankings.csv'):
                self.assertEqual((out/name).read_bytes(), (self.results/'derived'/name).read_bytes())
            result = support.run(self.results, Path(tmp)/'support')
        self.assertEqual(result['paired_input_configurations_per_carrier'], 25344)
        self.assertEqual(result['supports']['paired_nonempty']['configurations_per_carrier'], 24561)
        self.assertEqual(result['supports']['paired_equal_survivors']['configurations_per_carrier'], 17883)


if __name__ == '__main__':
    unittest.main()
