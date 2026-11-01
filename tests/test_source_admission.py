import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from covewm.benchmark import (CarrierState, carrier_only_states, extract_carriers,
                             payload_bits, render_program)
from covewm.source_admission import AdmissionError, admit_python
from covewm.tasks import TASK_BY_NAME


class SourceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.task = 'leap_year'
        self.template = TASK_BY_NAME[self.task].python_reference
        self.states = carrier_only_states(payload_bits(self.task, 'python', 0), 'hybrid')
        self.source = render_program(self.template, 'python', self.states)

    def test_every_receiver_reference_and_both_bits(self):
        for task, spec in TASK_BY_NAME.items():
            for bit in (0, 1):
                states = [CarrierState(i, 'lexical' if i < 12 else 'structural', bit, bit, True, '')
                          for i in range(24)]
                text = render_program(spec.python_reference, 'python', states)
                self.assertEqual(admit_python(task, text)['observed'], {i:bit for i in range(24)})

    def test_comments_blank_lines_and_deleted_sites(self):
        states = [copy.copy(s) for s in self.states if s.index % 3]
        text = render_program(self.template, 'python', states, formatted=True)
        self.assertEqual(admit_python(self.task, text)['observed'], {s.index:s.observed for s in states})
        text = render_program(self.template, 'python', [])
        self.assertEqual(admit_python(self.task, text)['observed'], {})

    def test_regex_acceptance_is_not_semantic_admission(self):
        # The old extractor sees the same bit, despite executable carrier code.
        bad = self.source.replace(' = 0', ' = 1 / 0', 1)
        self.assertEqual(extract_carriers(bad, 'python'), extract_carriers(self.source, 'python'))
        with self.assertRaises(AdmissionError): admit_python(self.task, bad)

    def test_changed_body_and_interface_reject(self):
        for bad in (self.source.replace('% 400', '% 800'), self.source.replace('solve(year)', 'solve(year=0)'),
                    self.source + '\nprint(1)\n', self.source.replace('return year', 'return locals() or year')):
            with self.subTest(bad=bad):
                with self.assertRaises(AdmissionError): admit_python(self.task, bad)

    def test_marker_or_name_spoof_rejects(self):
        for bad in (self.source.replace('WM_SITE 00', 'WM_SITE 01', 1),
                    self.source.replace('wm_bit_00', 'wm_bit_23', 1),
                    self.source.replace('# WM_SITE 00 LEXICAL', '"WM_SITE 00 LEXICAL"', 1),
                    self.source.replace('in ():', 'in (1,):', 1),
                    self.source.replace('if False:', 'if True:', 1)):
            if bad == self.source: continue
            with self.subTest(bad=bad):
                with self.assertRaises(AdmissionError): admit_python(self.task, bad)

    def test_fresh_local_condition_and_actual_result_control(self):
        # Representative normal execution of owned source is a separate
        # regression oracle, not the semantic proof or a new task sample.
        good, plain = {}, {}
        exec(compile(self.source, '<owned>', 'exec'), good)
        exec(compile(render_program(self.template, 'python', []), '<plain>', 'exec'), plain)
        self.assertTrue(admit_python(self.task, self.source)['admitted'])
        self.assertEqual([good['solve'](n) for n in range(1200,2001)],
                         [plain['solve'](n) for n in range(1200,2001)])
        first = 'wm_bit_00' if self.states[0].observed == 0 else 'wmBit00'
        bad = self.source.replace(first, 'year', 1)
        with self.assertRaises(AdmissionError): admit_python(self.task, bad)

if __name__ == '__main__':
    unittest.main()
