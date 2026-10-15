"""Owned metadata-only fixtures; the scientific campaign is never executed."""
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_all


class CommandMetadataTests(unittest.TestCase):
    def test_api_invocation_uses_fresh_output_not_parent_test_command(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"fresh-not-default"
            with patch.object(sys, "argv", ["unrelated-test-runner", "--test-only"]):
                record = run_all.producer_invocation(output)
            self.assertEqual(record["command_argv"][-2:], ["--out", str(output.resolve())])
            self.assertEqual(record["command_argv"][0], sys.executable)
            self.assertNotIn("--test-only", record["command_argv"])
            self.assertEqual(record["command_kind"], "python-api-reproduction")

    def test_both_command_sites_match_for_spaced_unicode_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"fresh 输出 & evidence"
            output.mkdir()
            argv = [sys.executable, "-O", "-B", str(Path(run_all.__file__).resolve()),
                    "--out", str(output)]
            run_all.write_run_metadata(output, "owned-node-fixture", argv)
            environment = json.loads((output/"environment.json").read_text(encoding="utf-8"))
            with (output/"results_manifest.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertTrue(rows)
            self.assertEqual(environment["command_argv"], argv)
            self.assertEqual(environment["command_kind"], "actual-cli")
            self.assertEqual(environment["command_cwd"], str(Path.cwd()))
            for row in rows:
                self.assertEqual(row["producer_command"], environment["command"])
                self.assertEqual(json.loads(row["producer_argv"]), argv)
                self.assertEqual(row["producer_cwd"], environment["command_cwd"])
                self.assertEqual(row["producer_command_format"], environment["command_format"])

    def test_readable_commands_quote_for_posix_and_windows(self):
        argv = ["/python path/python", "script path/run_all.py", "--out", "fresh 空格/O'Reilly & x"]
        rendered = run_all.readable_command(argv, platform_name="posix")
        self.assertEqual(shlex.split(rendered), argv)
        windows_argv = [r"C:\Python Tools\python.exe", r"C:\artifact\run_all.py",
                        "--out", r"C:\fresh runs\含 空格"]
        self.assertEqual(run_all.readable_command(windows_argv, platform_name="nt"),
                         '"C:\\Python Tools\\python.exe" C:\\artifact\\run_all.py --out "C:\\fresh runs\\含 空格"')

    def test_cli_preserves_interpreter_flags_and_supplied_relative_output(self):
        supplied = ["run_all.py", "--out", "fresh 相对 路径"]
        original = ["python", "-O", "-B", *supplied]
        with patch.object(sys, "argv", supplied), patch.object(sys, "orig_argv", original), \
             patch.object(run_all, "run", return_value={}) as runner, \
             contextlib.redirect_stdout(io.StringIO()):
            run_all.main()
        runner.assert_called_once_with(Path(supplied[-1]).resolve(),
                                       invocation_argv=[sys.executable, *original[1:]])

    def test_existing_output_prevents_metadata_and_campaign_work(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"retained 输出"
            output.mkdir()
            sentinel = output/"observation.txt"
            sentinel.write_bytes(b"owned retained observation\n")
            with patch.object(run_all, "write_run_metadata") as metadata, \
                 patch.object(run_all, "validate_domains") as domains:
                with self.assertRaises(FileExistsError):
                    run_all.run(output, invocation_argv=["python", "run_all.py", "--out", str(output)])
            metadata.assert_not_called()
            domains.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"owned retained observation\n")

    def test_metadata_inventory_preserves_data_and_excludes_own_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"fresh evidence"
            output.mkdir()
            payload = b"owned fixture, not a scientific measurement\n"
            (output/"fixture.txt").write_bytes(payload)
            run_all.write_run_metadata(output, "owned-node-fixture")
            with (output/"results_manifest.csv").open(newline="", encoding="utf-8") as stream:
                rows = {r["relative_path"]: r for r in csv.DictReader(stream)}
            self.assertEqual(set(rows), {"fixture.txt", "environment.json"})
            self.assertEqual(rows["fixture.txt"]["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(int(rows["fixture.txt"]["bytes"]), len(payload))
            self.assertEqual((output/"fixture.txt").read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
