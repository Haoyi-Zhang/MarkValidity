#!/usr/bin/env python3
"""Fresh, non-destructive evidence audit with owned native semantic controls.

No attack generator, downloaded program, model, or transfer-corpus intervention
is executed. Historical state rows are inputs, not newly generated experiments.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
from covewm.benchmark import (carrier_only_states, evaluate_python, first_mismatch,
                             payload_bits, render_program, sha256_text)
from covewm.metrics import roc_auc
from covewm.tasks import TASKS, domain_cases, validate_domains
from check_joint_evidence import boolean, indexed, run as joint_run
from run_all import validate_semantic_evidence


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def rank_auc(labels, scores):
    """Independent pooled average-rank identity; same admitted paired data."""
    if len(labels) != len(scores) or any(label not in (0, 1) for label in labels):
        raise ValueError("complete pairs with binary labels required")
    if any(not isinstance(s, (int, float)) or not math.isfinite(s) for s in scores):
        raise ValueError("finite scores required")
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        raise ValueError("both classes required")
    ordered = sorted(zip(scores, labels))
    rank_sum, cursor = Fraction(0), 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
            end += 1
        rank_sum += Fraction(cursor + 1 + end, 2) * sum(label for _, label in ordered[cursor:end])
        cursor = end
    return (rank_sum - Fraction(positives * (positives + 1), 2)) / (positives * negatives)


def retained_analysis(results, output):
    names = ("raw/cross_language_parity.csv", "raw/mutants.csv", "raw/semantic_audit.csv",
             "raw/diagnostic_pairs.csv", "derived/semantic_proxy_auc.csv",
             "derived/contextual_semantic_proxy_auc.csv")
    manifest = read_csv(results / "results_manifest.csv")
    manifest_index = indexed(manifest, lambda r:r["relative_path"], {r["relative_path"] for r in manifest})
    hashes = {}
    for name in names:
        data = (results / name).read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        if hashes[name] != manifest_index[name]["sha256"] or len(data) != int(manifest_index[name]["bytes"]):
            raise ValueError("retained input integrity failure: " + name)
    parity = read_csv(results / names[0])
    mutants = read_csv(results / names[1])
    audits = read_csv(results / names[2])
    typed = []
    for rows, flags in ((parity, ("equal",)), (mutants, ("parse_ok", "full_domain_equal")),
                        (audits, ("parse_ok", "bounded_equivalent"))):
        converted = []
        for row in rows:
            item = dict(row, domain_cases=int(row["domain_cases"]))
            for flag in flags:
                item[flag] = boolean(row[flag])
            if "mutant_id" in row:
                item["mutant_id"] = int(row["mutant_id"])
            converted.append(item)
        typed.append(converted)
    validate_semantic_evidence(*typed)
    diagnostics = read_csv(results / names[3])
    expected_ids = {f"mutant::{r['task']}::{r['language']}::{r['mutant_id']}" for r in mutants}
    expected_ids |= {f"audit::{r['task']}::{r['language']}::{r['scheme']}::{r['condition']}" for r in audits}
    index = indexed(diagnostics, lambda r:r["pair_id"], expected_ids)
    expected_labels = {f"mutant::{r['task']}::{r['language']}::{r['mutant_id']}":
                       (boolean(r["parse_ok"]) and boolean(r["full_domain_equal"]), boolean(r["nominal_equal"]))
                       for r in mutants}
    expected_labels.update({f"audit::{r['task']}::{r['language']}::{r['scheme']}::{r['condition']}":
                            (boolean(r["parse_ok"]) and boolean(r["bounded_equivalent"]), boolean(r["nominal_equal"]))
                            for r in audits})
    for identifier, row in index.items():
        if (boolean(row["bounded_equivalent"]), boolean(row["nominal_test_pass"])) != expected_labels[identifier]:
            raise ValueError("diagnostic evidence-label mismatch: " + identifier)
        parts = identifier.split("::")
        if (row["task"], row["language"]) != (parts[1], parts[2]):
            raise ValueError("diagnostic context mismatch")
    metrics = sorted(k for k in diagnostics[0] if k.endswith("_similarity"))
    indicators = ["nominal_test_pass_rate"] + metrics
    pooled = indexed(read_csv(results / names[4]), lambda r:r["indicator"], set(indicators))
    contextual = indexed(read_csv(results / names[5]),
                         lambda r:(r["context_kind"], r["context"], r["indicator"]),
                         {("task", t.name, m) for t in TASKS for m in indicators} |
                         {("task-language", f"{t.name}:{lang}", m) for t in TASKS
                          for lang in ("python", "javascript") for m in indicators})
    comparisons = []
    contexts = [("pooled", "all", diagnostics)]
    contexts += [("task", t.name, [r for r in diagnostics if r["task"] == t.name]) for t in TASKS]
    contexts += [("task-language", f"{t.name}:{lang}", [r for r in diagnostics
                 if r["task"] == t.name and r["language"] == lang])
                 for t in TASKS for lang in ("python", "javascript")]
    for kind, context, subset in contexts:
        labels = [int(r["bounded_equivalent"]) for r in subset]
        for indicator in indicators:
            field = "nominal_test_pass" if indicator == "nominal_test_pass_rate" else indicator
            scores = [float(r[field]) for r in subset]
            value, reference = roc_auc(labels, scores), rank_auc(labels, scores)
            old = pooled[indicator] if kind == "pooled" else contextual[(kind, context, indicator)]
            if value != float(reference) or not math.isclose(value, float(old["roc_auc"]), abs_tol=5e-13, rel_tol=0):
                raise ValueError("same-information AUC mismatch")
            if kind != "pooled" and int(old["rows"]) != len(subset):
                raise ValueError("contextual AUC denominator mismatch")
            comparisons.append(dict(context_kind=kind, context=context, indicator=indicator,
                                    rows=len(subset), positives=sum(labels), negatives=len(labels)-sum(labels),
                                    auc=value, rank_reference_exact=str(reference), retained_auc=old["roc_auc"]))
    write_csv(output / "auc-comparisons.csv", comparisons)
    joint = joint_run(results, output / "joint")
    return dict(input_sha256={**hashes, **joint["input_sha256"]}, semantic_gate="PASS",
                diagnostic_pairs=len(diagnostics), auc_comparisons=len(comparisons), joint=joint)


def owned_native(results, output):
    """Execute only reviewed owned references, existing mutants, and carrier-only no-ops."""
    validate_domains()
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node is required for the owned JavaScript control path")
    input_spec = {"tasks": {}}
    python_results, sources = {}, {}
    for task in TASKS:
        cases = domain_cases(task.name)
        nominal = [list(c) for c in task.nominal_cases]
        task_spec = dict(cases=cases, nominal_cases=nominal)
        for language in ("python", "javascript"):
            template = task.python_reference if language == "python" else task.javascript_reference
            mutants = task.python_mutants if language == "python" else task.javascript_mutants
            programs = [dict(id=f"reference::{task.name}::{language}", role="reference",
                             source=render_program(template, language, None))]
            programs += [dict(id=f"mutant::{task.name}::{language}::{i}", role="mutant", source=s.rstrip()+"\n")
                         for i, s in enumerate(mutants, 1)]
            programs += [dict(id=f"audit::{task.name}::{language}::{scheme}::carrier_only", role="audit",
                             source=render_program(template, language,
                                carrier_only_states(payload_bits(task.name, language, 0), scheme)))
                         for scheme in ("lexical", "structural", "hybrid")]
            task_spec[language] = programs
            for p in programs:
                sources[p["id"]] = sha256_text(p["source"])
            if language == "python":
                reference, _ = evaluate_python(programs[0]["source"], cases)
                reference_nominal, _ = evaluate_python(programs[0]["source"], nominal)
                for p in programs:
                    values, digest = evaluate_python(p["source"], cases)
                    nominal_values, nominal_digest = evaluate_python(p["source"], nominal)
                    mismatch = first_mismatch(reference, values)
                    python_results[p["id"]] = dict(id=p["id"], role=p["role"], parse_ok=True,
                        domain_hash=digest, nominal_hash=nominal_digest, domain_equal=mismatch is None,
                        nominal_equal=first_mismatch(reference_nominal, nominal_values) is None,
                        first_mismatch_index=mismatch, error="")
        input_spec["tasks"][task.name] = task_spec
    write_json(output / "owned-inputs.json", input_spec)
    node_spec = {"tasks": {name:dict(cases=spec["cases"], nominal_cases=spec["nominal_cases"],
                                    programs=spec["javascript"]) for name, spec in input_spec["tasks"].items()}}
    write_json(output / "node-inputs.json", node_spec)
    completed = subprocess.run([node, str(HERE / "js/batch_runner.js"), str(output / "node-inputs.json")],
                               capture_output=True, text=True, timeout=180)
    (output / "node-stdout.json").write_text(completed.stdout, encoding="utf-8")
    (output / "node-stderr.txt").write_text(completed.stderr, encoding="utf-8")
    completed.check_returncode()
    native = json.loads(completed.stdout)
    javascript_results = {p["id"]:p for task in native["tasks"].values() for p in task["programs"]}
    write_json(output / "python-observations.json", python_results)
    archive_parity = {r["task"]:r for r in read_csv(results / "raw/cross_language_parity.csv")}
    archive_mutants = {f"mutant::{r['task']}::{r['language']}::{r['mutant_id']}":r
                       for r in read_csv(results / "raw/mutants.csv")}
    archive_audits = {f"audit::{r['task']}::{r['language']}::{r['scheme']}::{r['condition']}":r
                      for r in read_csv(results / "raw/semantic_audit.csv")}
    rows = []
    for identifier, r in {**python_results, **javascript_results}.items():
        _, task, language, *_ = identifier.split("::")
        if not r["parse_ok"] or (r["role"] == "mutant") == r["domain_equal"]:
            raise ValueError("owned native semantic obligation failed: " + identifier)
        if r["role"] == "reference":
            old = archive_parity[task]
            agrees = r["domain_hash"] == old[f"{language}_hash"]
        else:
            old = archive_mutants[identifier] if r["role"] == "mutant" else archive_audits[identifier]
            agrees = (sources[identifier] == old["source_sha256"] and
                      r["nominal_equal"] == boolean(old["nominal_equal"]) and
                      r["first_mismatch_index"] == (int(old["first_mismatch_index"]) if old["first_mismatch_index"] else None))
        if not agrees:
            raise ValueError("owned native disagreement with retained evidence: " + identifier)
        rows.append(dict(id=identifier, source_sha256=sources[identifier], **{k:v for k,v in r.items() if k != "id"},
                         retained_evidence_agrees=agrees))
    if len(rows) != 168 or sum(r["role"] == "mutant" and r["nominal_equal"] for r in rows) != 6:
        raise ValueError("owned native coverage/survivor mismatch")
    for task in TASKS:
        if python_results[f"reference::{task.name}::python"]["domain_hash"] != javascript_results[f"reference::{task.name}::javascript"]["domain_hash"]:
            raise ValueError("owned reference language mismatch")
    write_csv(output / "owned-native-observations.csv", rows)
    return dict(node=native["node_version"], node_executable=node, programs=168,
                references=24, effective_mutants=72, nominal_surviving_mutants=6,
                carrier_only_noop_programs=72, cases_per_language=33013,
                scope="Owned fixtures only; no new targeted interventions, removal campaign, or transfer-project execution.")


def run(results, output):
    results, output = Path(results).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(results) or results.is_relative_to(output):
        raise ValueError("fresh output disjoint from retained inputs required")
    output.mkdir(parents=True, exist_ok=False)
    start, cpu = time.perf_counter(), time.process_time()
    timings = {}
    try:
        checkpoint = time.perf_counter()
        retained = retained_analysis(results, output)
        timings["retained_data_analysis_wall_seconds"] = time.perf_counter()-checkpoint
        checkpoint = time.perf_counter()
        native = owned_native(results, output)
        timings["owned_native_setup_execution_and_archive_comparison_wall_seconds"] = time.perf_counter()-checkpoint
        status, error = "PASS", None
    except Exception as exc:
        status, error = "FAIL", f"{type(exc).__name__}: {exc}"
        retained, native = locals().get("retained"), locals().get("native")
    code = [Path(__file__), HERE / "check_joint_evidence.py", HERE / "run_all.py", HERE / "recheck_extended.py",
            HERE / "js/batch_runner.js"] + sorted((HERE / "src/covewm").glob("*.py"))
    receipt = dict(status=status, error=error, command=sys.argv, input_directory=str(results),
        executed_at_utc=datetime.now(timezone.utc).isoformat(), retained_analysis=retained, owned_native=native,
        environment=dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                         dependencies="Python/Node standard libraries only"),
        cost_scope="Includes input integrity, schema/coverage, same-info baselines, native specification setup, both runtimes, serialization and archive comparison. No speedup or upstream cost comparison.",
        timings={**timings, "full_workflow_wall_seconds_before_receipt":time.perf_counter()-start,
                 "parent_python_cpu_seconds":time.process_time()-cpu,
                 "child_node_cpu_seconds":"NOT_MEASURED"},
        source_sha256={p.resolve().relative_to(HERE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in code},
        skips=["No regeneration of the historical 76032-row indexed-state response matrix or targeted source interventions.",
               "No full upstream model/checkpoint/generation runs; STONE naturalness remains undefined.",
               "No transfer-corpus transformations or execution, new null-simulation campaign, or CI runner execution."],
        closed_loop_complete=False, scientific_acceptance=False)
    write_json(output / "receipt.json", receipt)
    # Includes raw inputs/outputs; excludes this manifest's own bytes.
    write_json(output / "output-inventory.json", {p.relative_to(output).as_posix():dict(
        sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)
        for p in sorted(output.rglob("*")) if p.is_file()})
    if error:
        raise RuntimeError(error)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=HERE / "results/current/results")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results, args.out), indent=2, sort_keys=True))
