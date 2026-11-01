"""Current static-validation regressions; no task or upstream program executes.

Faults below are in-memory copies of retained rows, never new research evidence.
"""
import csv
import gzip
import hashlib
import io
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
import summarize_evidence_policies as policy
import check_source_detection as bridge
from covewm import benchmark
from covewm.source_admission import AdmissionError
from covewm.tasks import TASKS,domain_cases


def csv_bytes(rows, omit=None):
    buffer = io.StringIO(newline='')
    fields = [f for f in rows[0] if f != omit]
    writer = csv.DictWriter(buffer, fields, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode('utf-8')


class EvidencePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def read(value):
            return list(csv.DictReader(io.StringIO(value.decode('utf-8'))))
        cls.raw = read((ROOT/'results/raw/robustness.csv').read_bytes())
        cls.proof = read(gzip.decompress((ROOT/'results/source_admission/rows.csv.gz').read_bytes()))
        cls.observed = read((ROOT/'results/source_detection/rows.csv').read_bytes())
        cls.dense = policy.indexed(cls.raw, policy.key, policy.expected_keys(), 'dense inventory')
        cls.first_proof = min(range(len(cls.proof)), key=lambda i: policy.key(cls.proof[i]))
        cls.executed = next(i for i, r in enumerate(cls.observed)
                            if (r['task'], r['language'], r['scheme'], r['condition'])
                            == ('armstrong', 'javascript', 'hybrid', 'format'))

    def run_replaced_input(self, relative, data):
        """Exercise the public receiving boundary with virtual bytes only."""
        original = Path.read_bytes
        path = ROOT/relative
        def read(p):
            return data if p == path else original(p)
        with patch.object(Path, 'read_bytes', read):
            return policy.summarize()

    def test_policies_do_not_relabel_execution(self):
        original = policy.admit_python
        calls = 0
        def admit(task, source):
            nonlocal calls
            calls += 1
            return original(task, source)
        # Neither old unbound success summary is an acceptance credential.
        read_bytes = Path.read_bytes
        def guard_read(p):
            if p in (ROOT/'results/source_admission/summary.json',
                     ROOT/'results/evidence-policies/summary.json'):
                raise AssertionError('historical success receipt must not replace current admission')
            return read_bytes(p)
        with patch.object(policy, 'admit_python', admit), \
             patch.object(Path, 'read_bytes', guard_read), \
             patch.object(benchmark, 'compile_python', side_effect=AssertionError('task execution forbidden')), \
             patch.object(benchmark, 'evaluate_python', side_effect=AssertionError('task execution forbidden')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('child execution forbidden')):
            r=policy.summarize()
        self.assertEqual((r['execution_only']['known'],r['execution_only']['detected']),(432,122))
        self.assertEqual((r['proof_supported']['known'],r['proof_supported']['detected']),(38232,17955))
        self.assertEqual(r['proof_supported']['upper_numerator'],55755)
        self.assertEqual((r['proof_admitted_python_detected'],r['executed_javascript_detected']),(17893,62))
        self.assertFalse(r['historical_labels_changed'])
        self.assertEqual(r['task_programs_executed'],0)
        scope = r['validation_scope']
        self.assertEqual(scope['kind'], 'current-deterministic-static-revalidation')
        self.assertFalse(scope['historical_success_receipt_restored'])
        self.assertFalse(scope['historical_research_budgets_changed'])
        self.assertEqual(scope['proof_configurations_revalidated'], len(self.proof))
        self.assertEqual(calls, len({(p['task'], p['source_sha256']) for p in self.proof}))
        self.assertEqual(scope['distinct_task_source_admissions'], calls)
        self.assertEqual((scope['maximum_source_admissions'], scope['wall_limit_seconds']), (38016, 480))
        self.assertEqual(scope['carrier_only_controls_checked'], 72)
        self.assertEqual(scope['executed_dense_links_source_bound'], 432)
        self.assertEqual(scope['upstream_programs_executed'], 0)
        self.assertEqual(scope['model_API_calls'], 0)
        for name, digest in r['input_bindings'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest)

    def test_payload_shift_refused_with_unchanged_row_count_and_detection(self):
        rows = list(self.observed)
        rows[self.executed] = dict(rows[self.executed], payload_index='1')
        self.assertEqual(len(rows), len(self.observed))
        self.assertEqual(rows[self.executed]['detected'], self.observed[self.executed]['detected'])
        with self.assertRaisesRegex(ValueError, 'executed source configuration mismatch'):
            self.run_replaced_input('results/source_detection/rows.csv', csv_bytes(rows))

    def test_execution_source_hash_replacement_and_missing_column_refused(self):
        for omit in (False, True):
            rows = list(self.observed)
            rows[self.executed] = dict(rows[self.executed], source_sha256='0'*64)
            with self.subTest(missing=omit), self.assertRaisesRegex(ValueError, 'source.*identity|source_sha256'):
                self.run_replaced_input('results/source_detection/rows.csv',
                                        csv_bytes(rows, 'source_sha256' if omit else None))

    def test_execution_cannot_inherit_a_changed_retained_source(self):
        original = bridge.render_program
        with patch.object(bridge, 'render_program', side_effect=lambda *a, **kw: original(*a, **kw)+'\n'), \
             self.assertRaisesRegex(ValueError, 'not the semantically audited source'):
            policy.summarize()

    def test_excluded_carrier_control_cannot_silently_become_a_dense_link(self):
        rows = list(self.observed)
        index = next(i for i, r in enumerate(rows) if r['condition'] == 'carrier_only')
        rows[index] = dict(rows[index], dense_linked='True')
        with self.assertRaisesRegex(ValueError, 'evidence flag mismatch'):
            self.run_replaced_input('results/source_detection/rows.csv', csv_bytes(rows))

    def test_dense_unregistered_configuration_refused_without_count_change(self):
        rows = list(self.raw)
        rows[0] = dict(rows[0], task='unregistered')
        self.assertEqual(len(rows), len({policy.key(r) for r in rows}))
        with self.assertRaisesRegex(ValueError, 'dense inventory exact key coverage mismatch'):
            self.run_replaced_input('results/raw/robustness.csv', csv_bytes(rows))

    def test_proof_unregistered_configuration_and_duplicate_for_missing_refused(self):
        for replacement in (dict(self.proof[self.first_proof], task='unregistered'), self.proof[-1]):
            rows = list(self.proof)
            rows[self.first_proof] = replacement
            with self.subTest(replacement=replacement['task']), \
                 patch.object(policy, 'admit_python') as admit, \
                 self.assertRaisesRegex(ValueError, 'Python proof inventory (exact key coverage mismatch|duplicate key)'):
                policy.validate_proofs(rows, self.dense, policy.time.monotonic())
            admit.assert_not_called()

    def test_proof_source_hash_replacement_and_missing_column_refused(self):
        for omit in (False, True):
            rows = list(self.proof)
            rows[self.first_proof] = dict(rows[self.first_proof], source_sha256='0'*64)
            with self.subTest(missing=omit), self.assertRaisesRegex(ValueError, 'source.*identity|source_sha256'):
                self.run_replaced_input('results/source_admission/rows.csv.gz',
                                        gzip.compress(csv_bytes(rows, 'source_sha256' if omit else None)))

    def test_proof_output_payload_permutation_refused_even_with_complete_keys(self):
        rows = list(self.proof)
        first = self.first_proof
        second = next(i for i, row in enumerate(rows)
                      if policy.key(row)[:-1] == policy.key(rows[first])[:-1] and row['payload_index'] == '1')
        rows[first] = dict(rows[first], payload_index='1')
        rows[second] = dict(rows[second], payload_index='0')
        # Exact inventory and every reported positive count still pass. Sources do not.
        self.assertEqual(set(policy.key(r) for r in rows), set(policy.key(r) for r in self.proof))
        self.assertEqual(sum(int(r['detected']) for r in rows), sum(int(r['detected']) for r in self.proof))
        with self.assertRaisesRegex(ValueError, 'proof source identity disagrees'):
            self.run_replaced_input('results/source_admission/rows.csv.gz', gzip.compress(csv_bytes(rows)))

    def test_proof_detected_counts_tampering_refused(self):
        rows = list(self.proof)
        original = rows[self.first_proof]
        self.assertEqual((original['surviving_sites'], original['match_count']), ('24', '24'))
        rows[self.first_proof] = dict(original, match_count='23')
        with self.assertRaisesRegex(ValueError, 'proof record disagrees with dense detection'):
            policy.validate_proofs(rows, self.dense, policy.time.monotonic())

    def test_true_historical_proof_flag_cannot_replace_current_ast_admission(self):
        with patch.object(policy, 'admit_python', side_effect=AdmissionError('current erasure rejected')) as admit, \
             self.assertRaisesRegex(ValueError, 'current erasure rejected'):
            policy.validate_proofs(self.proof, self.dense, policy.time.monotonic())
        self.assertEqual(admit.call_count, 1)

    def test_ast_observations_must_match_actual_source_and_states(self):
        with patch.object(policy, 'admit_python', return_value={'admitted': True, 'observed': {}}), \
             self.assertRaisesRegex(ValueError, 'AST/source/state observations disagree'):
            policy.validate_proofs(self.proof, self.dense, policy.time.monotonic())

    def test_proof_execution_overlap_compares_source_identity_and_detection(self):
        k = ('owned', 'python', 'hybrid', 'format', '1.0', 0)
        proof = {k: ('0'*64, (24, 24, 1))}
        for value in (('1'*64, (24, 24, 1)), ('0'*64, (24, 23, 1))):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'overlap disagrees'):
                policy.check_overlap(proof, {k: value})

    def test_source_admission_cap_is_fail_closed_before_the_next_call(self):
        with patch.object(policy, 'MAX_SOURCE_ADMISSIONS', 0), patch.object(policy, 'admit_python') as admit, \
             self.assertRaisesRegex(ValueError, 'source-admission limit exceeded'):
            policy.validate_proofs(self.proof, self.dense, policy.time.monotonic())
        admit.assert_not_called()

    def test_static_deadline_is_fail_closed_before_and_after_admission(self):
        with patch.object(policy.time, 'monotonic', return_value=480), \
             patch.object(policy, 'admit_python') as admit, self.assertRaises(TimeoutError):
            policy.validate_proofs(self.proof, self.dense, 0)
        admit.assert_not_called()
        now = [0]
        original = policy.admit_python
        def expired_after_admission(task, source):
            result = original(task, source)
            now[0] = 480
            return result
        with patch.object(policy.time, 'monotonic', side_effect=lambda: now[0]), \
             patch.object(policy, 'admit_python', expired_after_admission), self.assertRaises(TimeoutError):
            policy.validate_proofs(self.proof, self.dense, 0)

    def test_exact_domain_sizes_and_hamming_tail(self):
        domains={t.name:domain_cases(t.name) for t in TASKS}
        self.assertEqual(sum(map(len,domains.values())),33013)
        self.assertTrue(all(len(domains[t.name])==t.domain_size for t in TASKS))
        self.assertEqual(domains['hamming'][-13:],[['GT',w] for w in ['', 'A','C','AA','AC','CA','CC','AAA','AAC','ACA','ACC','CAA','CAC']])

if __name__=='__main__':unittest.main()
