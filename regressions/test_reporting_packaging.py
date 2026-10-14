"""Reporting obligations remain executable in flat and integrated packages."""
from pathlib import Path
import tempfile
import unittest

from test_reporting_contract import manuscript_text


class ReportingPackagingTests(unittest.TestCase):
    def test_flat_package_reads_required_reporting_passage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / 'artifact'
            (artifact / 'manuscript-reporting').mkdir(parents=True)
            expected = 'separate weightings rather than a common cross-carrier comparison\n'
            (artifact / 'manuscript-reporting/main.tex').write_text(expected, encoding='utf-8')
            self.assertEqual(manuscript_text('main.tex', artifact, root / 'paper'), expected)

    def test_missing_passage_is_an_error_even_with_integrated_manuscript(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / 'paper'
            paper.mkdir()
            (paper / 'main.tex').write_text('a manuscript\n', encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                manuscript_text('main.tex', root / 'artifact', paper)

    def test_integrated_manuscript_must_contain_the_shipped_passage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, paper = root / 'artifact', root / 'paper'
            (artifact / 'manuscript-reporting').mkdir(parents=True)
            paper.mkdir()
            (artifact / 'manuscript-reporting/main.tex').write_text('declared comparison\n', encoding='utf-8')
            (paper / 'main.tex').write_text('a different comparison\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                manuscript_text('main.tex', artifact, paper)
            (paper / 'main.tex').write_text('before\ndeclared comparison\nafter\n', encoding='utf-8')
            self.assertIn('declared comparison', manuscript_text('main.tex', artifact, paper))


if __name__ == '__main__':
    unittest.main()
