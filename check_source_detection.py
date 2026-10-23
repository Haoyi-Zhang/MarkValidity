"""Bind retained semantic source identities to fresh source-extracted decisions.

Only the study's owned transparent carrier renderers and regex extractor run.
No task program, upstream watermark system or third-party module executes.
"""
from __future__ import annotations
import argparse
import csv
from fractions import Fraction
import hashlib
import io
import itertools
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'src'))
from covewm.benchmark import (SCHEMES, ATTACKS, CarrierState, attacked_states,
                             carrier_only_states, payload_bits, render_program,
                             extract_carriers, detector)
from covewm.tasks import TASK_BY_NAME


def read_table(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8'))))


def checked_input(results, relative, manifest):
    data = (results / relative).read_bytes()
    row = manifest.get(relative)
    if row is None or int(row['bytes']) != len(data) or row['sha256'] != hashlib.sha256(data).hexdigest():
        raise ValueError('retained input does not match its manifest: ' + relative)
    return data


def analyze(results):
    results = Path(results).resolve()
    manifest_rows = read_table(results / 'results_manifest.csv')
    manifest = {r['relative_path']: r for r in manifest_rows}
    if len(manifest) != len(manifest_rows):
        raise ValueError('duplicate retained manifest member')
    inputs = {name: checked_input(results, name, manifest) for name in
              ('raw/semantic_audit.csv', 'raw/robustness.csv')}
    audits = list(csv.DictReader(io.StringIO(inputs['raw/semantic_audit.csv'].decode('utf-8'))))
    dense_rows = list(csv.DictReader(io.StringIO(inputs['raw/robustness.csv'].decode('utf-8'))))
    def dense_key(row):
        return row['task'], row['language'], row['scheme'], row['attack'], row['severity'], int(row['payload_index'])
    dense = {dense_key(row): row for row in dense_rows}
    expected_dense = set(itertools.product(TASK_BY_NAME, ('python', 'javascript'),
                                          SCHEMES, ATTACKS,
                                          (f'{i / 10:.1f}' for i in range(11)), range(16)))
    if set(dense) != expected_dense or len(dense_rows) != 76032:
        raise ValueError('dense inventory is not complete and unique')
    expected = {(task, lang, scheme, condition) for task in TASK_BY_NAME
                for lang in ('python', 'javascript') for scheme in SCHEMES
                for condition in ('carrier_only',) + ATTACKS}
    keyed = {(r['task'], r['language'], r['scheme'], r['condition']): r for r in audits}
    if set(keyed) != expected or len(keyed) != len(audits):
        raise ValueError('semantic inventory is not complete and unique')
    rows, snapshots, source_ids = [], [], set()
    for key, audit in sorted(keyed.items()):
        task, language, scheme, condition = key
        spec = TASK_BY_NAME[task]
        if int(audit['domain_cases']) != spec.domain_size or audit['parse_ok'] != 'True' or audit['bounded_equivalent'] != 'True':
            raise ValueError('invalid retained semantic premise')
        expected_bits = payload_bits(task, language, 0)
        if condition == 'carrier_only':
            states = carrier_only_states(expected_bits, scheme)
        else:
            states, _ = attacked_states(expected_bits, scheme, condition, 1.0, task, language, 0)
        template = spec.python_reference if language == 'python' else spec.javascript_reference
        source = render_program(template, language, states, formatted=condition == 'format')
        identity = hashlib.sha256(source.encode('utf-8')).hexdigest()
        if identity != audit['source_sha256']:
            raise ValueError('reconstructed source is not the semantically audited source')
        extracted = extract_carriers(source, language)
        state_observations = {s.index: s.observed for s in states if s.present}
        if extracted != state_observations:
            raise ValueError('render/extract observation differs from indexed carrier state')
        observed = [CarrierState(i, s.channel, expected_bits[i], extracted.get(i, 0),
                                 i in extracted, 'source-extracted') for i, s in enumerate(states)]
        result = detector(observed)
        linked = condition != 'carrier_only'
        if linked:
            model = dense[(task, language, scheme, condition, '1.0', 0)]
            for field in ('surviving_sites', 'match_count', 'detected'):
                if int(model[field]) != result[field]:
                    raise ValueError('source-extracted decision differs from the mapped dense row')
        rows.append(dict(task=task, language=language, scheme=scheme, condition=condition,
                         payload_index=0, severity='1.0' if linked else '',
                         source_sha256=identity, retained_semantic_label=True,
                         source_identity_matches_retained_audit=True,
                         dense_linked=linked, **result))
        snapshots.append(dict(task=task, language=language, scheme=scheme, condition=condition,
                              source_sha256=identity, source=source))
        source_ids.add(identity)
    linked = [r for r in rows if r['dense_linked']]
    positives = sum(r['detected'] for r in linked)
    n, k = len(dense_rows), len(linked)
    # Outside this directly extracted subset both source-level decision and
    # validity remain unobserved. Do not substitute the dense model's decision.
    summary = dict(source_extraction_rows=len(rows), unique_source_identities=len(source_ids),
                   dense_source_validity_detection_links=k, positive_linked_decisions=positives,
                   other_dense_rows_unmeasured=n-k, historical_semantic_evaluations_reused=k,
                   new_program_executions=0, new_upstream_system_executions=0,
                   source_valid_joint_full_universe_lower=str(Fraction(positives, n)),
                   source_valid_joint_full_universe_upper=str(Fraction(positives+n-k, n)),
                   observed_detector='declared marker-assisted regex extractor, not a general language parser',
                   scope='source identity and extraction bridge for payload zero/full severity; not the full matrix or external systems',
                   input_sha256={name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()})
    summary['per_scheme'] = {scheme: {
        'source_extraction_rows': sum(r['scheme'] == scheme for r in rows),
        'dense_links': sum(r['scheme'] == scheme for r in linked),
        'positive_linked_decisions': sum(r['detected'] for r in linked if r['scheme'] == scheme)}
        for scheme in SCHEMES}
    summary['distinct_source_identities_in_dense_links'] = len({r['source_sha256'] for r in linked})
    summary['producer_sha256'] = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        for name in ('check_source_detection.py', 'src/covewm/benchmark.py', 'src/covewm/tasks.py')}
    return rows, snapshots, summary


def run(results, out):
    results, out = Path(results).resolve(), Path(out).resolve()
    if out.exists() or out.is_relative_to(results) or results.is_relative_to(out):
        raise ValueError('fresh output disjoint from retained input required')
    rows, snapshots, summary = analyze(results)
    out.mkdir(parents=True, exist_ok=False)
    with (out / 'rows.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    (out / 'sources.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in snapshots), encoding='utf-8', newline='\n')
    (out / 'summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='\n')
    table = ['\\begin{tabular}{@{}lrrr@{}}', '\\toprule',
             'Carrier & Extracted & Dense links & Positive \\\\', '\\midrule']
    for scheme, values in summary['per_scheme'].items():
        table.append(f"{scheme.capitalize()} & {values['source_extraction_rows']} & {values['dense_links']} & {values['positive_linked_decisions']} " + r'\\')
    table += ['\\bottomrule', '\\end{tabular}']
    (out / 'table.tex').write_text('\n'.join(table) + '\n', encoding='utf-8', newline='\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=HERE / 'results/current/results')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results, args.out), sort_keys=True))
