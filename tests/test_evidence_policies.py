"""Data-only policy recount and exact domain disclosure checks."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from summarize_evidence_policies import summarize
from covewm.tasks import TASKS,domain_cases

class EvidencePolicyTests(unittest.TestCase):
    def test_policies_do_not_relabel_execution(self):
        r=summarize()
        self.assertEqual((r['execution_only']['known'],r['execution_only']['detected']),(432,122))
        self.assertEqual((r['proof_supported']['known'],r['proof_supported']['detected']),(38232,17955))
        self.assertEqual(r['proof_supported']['upper_numerator'],55755)
        self.assertEqual((r['proof_admitted_python_detected'],r['executed_javascript_detected']),(17893,62))
        self.assertFalse(r['historical_labels_changed'])
        self.assertEqual(r['task_programs_executed'],0)
    def test_exact_domain_sizes_and_hamming_tail(self):
        domains={t.name:domain_cases(t.name) for t in TASKS}
        self.assertEqual(sum(map(len,domains.values())),33013)
        self.assertTrue(all(len(domains[t.name])==t.domain_size for t in TASKS))
        self.assertEqual(domains['hamming'][-13:],[['GT',w] for w in ['', 'A','C','AA','AC','CA','CC','AAA','AAC','ACA','ACC','CAA','CAC']])

if __name__=='__main__':unittest.main()
