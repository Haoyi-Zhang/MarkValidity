"""Retained-data receiver checks, stopped before any extended/native recheck."""
from contextlib import ExitStack
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RETAINED = Path(os.environ.get('COVEWM_RESULTS', ROOT / 'results/current/results'))
sys.path.insert(0, str(ROOT))
import recheck


class DataOnlyBoundary(Exception):
    pass


def forbidden(*args, **kwargs):
    raise AssertionError('extended/native execution or hashing is outside this contract')


class ExternalProtocolContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only the inert CSV/JSON prefix is admitted. Never import the producer.
        names = ('cross_language_parity', 'mutants', 'semantic_audit',
                 'metric_interventions', 'robustness', 'robustness_shard_0',
                 'robustness_shard_1')
        cls.raw = {f'raw/{name}.csv': recheck.read_csv(RETAINED / f'raw/{name}.csv')
                   for name in names}

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='markvalidity-protocol-contract-')
        self.addCleanup(temporary.cleanup)
        self.results = Path(temporary.name).resolve()
        self.assertFalse(self.results.is_relative_to(ROOT.parent.resolve()))
        (self.results / 'derived').mkdir()
        for name in ('summary.json', 'derived/external_protocol_replay.csv',
                     'derived/external_protocol_rankings.csv',
                     'derived/external_protocol_replay_summary.json'):
            shutil.copyfile(RETAINED / name, self.results / name)

    def write_csv(self, name, values):
        with (self.results / 'derived' / name).open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(values[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(values)

    def summary(self):
        path = self.results / 'derived/external_protocol_replay_summary.json'
        return json.loads(path.read_text(encoding='utf-8'))

    def write_summary(self, value):
        path = self.results / 'derived/external_protocol_replay_summary.json'
        path.write_text(json.dumps(value), encoding='utf-8')

    def check_prefix(self):
        read_csv = recheck.read_csv
        require = recheck.require

        def bounded_read(path):
            name = path.relative_to(self.results).as_posix()
            if name in self.raw:
                return self.raw[name]
            if name in ('derived/external_protocol_replay.csv',
                        'derived/external_protocol_rankings.csv'):
                return read_csv(path)
            raise AssertionError(f'outside data-only prefix: {name}')

        def bounded_require(condition, label, findings, detail=''):
            require(condition, label, findings, detail)
            if label == 'external_protocols::independent_reconstruction':
                raise DataOnlyBoundary()

        with ExitStack() as stack:
            stack.enter_context(patch.object(recheck, 'read_csv', bounded_read))
            stack.enter_context(patch.object(recheck, 'require', bounded_require))
            stack.enter_context(patch.object(recheck, 'recheck_extended', forbidden))
            stack.enter_context(patch.object(recheck, 'sha256_file', forbidden))
            stack.enter_context(patch.object(subprocess, 'Popen', forbidden))
            try:
                recheck.recheck(self.results)
            except DataOnlyBoundary:
                return
            self.fail('recheck did not stop at the data-only boundary')

    def assert_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'external_protocols::'):
            self.check_prefix()

    def test_retained_rows_accept_without_manifest_or_hashes(self):
        self.assertEqual(len(self.raw['raw/robustness.csv']), 76032)
        self.check_prefix()

    def test_each_csv_count_is_independently_checked_per_carrier(self):
        path = RETAINED / 'derived/external_protocol_replay.csv'
        original = recheck.read_csv(path)
        for index, row in enumerate(original):
            for field in ('total_rows', 'zero_surviving_site_rows', 'sweet_defined_rows'):
                with self.subTest(scheme=row['scheme'], field=field):
                    changed = [dict(value) for value in original]
                    changed[index][field] = '0'
                    self.write_csv(path.name, changed)
                    self.assert_rejected()

    def test_summary_robustness_count_is_independently_checked(self):
        value = self.summary()
        value['robustness_rows'] = 0
        self.write_summary(value)
        self.assert_rejected()

    def test_each_summary_zero_site_count_is_independently_checked(self):
        original = self.summary()
        for scheme in original['schemes']:
            with self.subTest(scheme=scheme):
                changed = json.loads(json.dumps(original))
                changed['zero_surviving_site_rows'][scheme] = 0
                self.write_summary(changed)
                self.assert_rejected()

    def test_consistently_zeroed_csv_and_json_do_not_replace_raw_counts(self):
        values = recheck.read_csv(self.results / 'derived/external_protocol_replay.csv')
        for row in values:
            row.update(total_rows='0', zero_surviving_site_rows='0', sweet_defined_rows='0')
        self.write_csv('external_protocol_replay.csv', values)
        value = self.summary()
        value.update(robustness_rows=0, winners={},
                     zero_surviving_site_rows={scheme: 0 for scheme in value['schemes']})
        self.write_summary(value)
        self.assert_rejected()

    def test_summary_winners_cannot_be_erased(self):
        value = self.summary()
        value['winners'] = {}
        self.write_summary(value)
        self.assert_rejected()

    def test_summary_zero_site_map_requires_exact_carrier_coverage(self):
        original = self.summary()
        variants = ({}, {**original['zero_surviving_site_rows'], 'unknown': 0})
        for counts in variants:
            with self.subTest(counts=counts):
                value = dict(original, zero_surviving_site_rows=counts)
                self.write_summary(value)
                self.assert_rejected()


if __name__ == '__main__':
    unittest.main()
