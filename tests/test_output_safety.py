"""Benign output-path controls; never execute the scientific campaign."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_all


class OutputSafetyTests(unittest.TestCase):
    def test_existing_directory_is_preserved_before_campaign_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "retained"
            output.mkdir()
            sentinel = output / "observation.txt"
            sentinel.write_bytes(b"owned retained observation\n")
            with patch.object(run_all, "validate_domains") as validate, \
                 patch.object(run_all, "program_sources", side_effect=AssertionError("campaign forbidden")):
                with self.assertRaises(FileExistsError):
                    run_all.run(output)
            validate.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"owned retained observation\n")

    def test_existing_empty_directory_is_also_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.mkdir()
            with patch.object(run_all, "validate_domains") as validate, \
                 patch.object(run_all, "program_sources", side_effect=AssertionError("campaign forbidden")):
                with self.assertRaises(FileExistsError):
                    run_all.run(output)
            validate.assert_not_called()
            self.assertEqual(list(output.iterdir()), [])

    def test_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "owned.txt"
            output.write_bytes(b"owned file\n")
            with patch.object(run_all, "validate_domains") as validate:
                with self.assertRaises(FileExistsError):
                    run_all.run(output)
            validate.assert_not_called()
            self.assertEqual(output.read_bytes(), b"owned file\n")

    def test_cli_requires_explicit_output_without_calling_runner(self):
        with patch.object(sys, "argv", ["run_all.py"]), \
             patch.object(run_all, "run") as runner, \
             contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as stopped:
                run_all.main()
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn("--out", error.getvalue())
        runner.assert_not_called()

    def test_fresh_output_reaches_setup_without_running_programs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new" / "results"
            with patch.object(run_all, "validate_domains", side_effect=RuntimeError("owned setup stop")):
                with self.assertRaisesRegex(RuntimeError, "owned setup stop"):
                    run_all.run(output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
