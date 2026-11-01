"""Render and statically admit the complete frozen Python state submatrix.

This is a new source-admission analysis, not a rerun of program semantics or a
replacement of historical labels. It keeps proof-derived admission separate
from executed equivalence observations and never invokes a model or upstream
application. A source identity may reuse its exact cached AST admission only.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import platform
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'src'))
from covewm.benchmark import (ATTACKS, SCHEMES, CarrierState, attacked_states,
    detector, extract_carriers, payload_bits, render_program)
from covewm.source_admission import admit_python
from covewm.tasks import TASK_BY_NAME
from check_source_detection import checked_input, read_table


def run(results, out):
    results, out = Path(results).resolve(), Path(out).resolve()
    if out.exists() or out.is_relative_to(results) or results.is_relative_to(out):
        raise ValueError('fresh output outside retained inputs required')
    out.mkdir(parents=True)
    registration = dict(configurations=38016, languages=['python'],
        selection='All frozen task/scheme/attack/severity/payload keys, not outcome selection',
        maximum_unique_source_admissions=38016, wall_limit_seconds=480,
        candidate_program_executions=0, upstream_executions=0, model_API_calls=0,
        historical_semantic_labels_overwritten=False,
        proof_contract='Exact inert-prefix erasure against the receiver task; result-only builtin-domain semantics')
    (out/'registration.json').write_text(json.dumps(registration,indent=2)+'\n',encoding='utf-8',newline='\n')
    start = time.monotonic()
    inputs = {}
    cache = {}
    rows = []
    summary = dict(status='FAILED_OR_PARTIAL', registration=registration)
    try:
        mr = read_table(results/'results_manifest.csv')
        manifest = {r['relative_path']: r for r in mr}
        if len(mr) != len(manifest): raise ValueError('duplicate input manifest')
        raw = checked_input(results, 'raw/robustness.csv', manifest)
        inputs['raw/robustness.csv'] = hashlib.sha256(raw).hexdigest()
        records = list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
        records = [r for r in records if r['language'] == 'python']
        def key(r): return (r['task'],r['scheme'],r['attack'],r['severity'],int(r['payload_index']))
        keys = {key(r) for r in records}
        expected = set(itertools.product(TASK_BY_NAME, SCHEMES, ATTACKS,
            (f'{i/10:.1f}' for i in range(11)), range(16)))
        if keys != expected or len(records) != 38016: raise ValueError('incomplete/duplicate Python submatrix')
        for number, r in enumerate(sorted(records,key=key),1):
            if time.monotonic()-start >= 480: raise TimeoutError('source admission wall cap')
            task,scheme,attack,severity,payload = key(r)
            bits = payload_bits(task,'python',payload)
            states,_ = attacked_states(bits,scheme,attack,float(severity),task,'python',payload)
            source = render_program(TASK_BY_NAME[task].python_reference,'python',states,
                                    formatted=attack=='format')
            identity = hashlib.sha256(source.encode('utf-8')).hexdigest()
            cached = (task,identity) in cache
            if not cached: cache[(task,identity)] = admit_python(task,source)
            admitted = cache[(task,identity)]
            actual = admitted['observed']
            if actual != {s.index:s.observed for s in states if s.present}:
                raise ValueError('AST and state observations disagree')
            if actual != extract_carriers(source,'python'):
                raise ValueError('AST and retained extractor observations disagree')
            observations = [CarrierState(i,s.channel,bits[i],actual.get(i,0),i in actual,'AST-admitted')
                            for i,s in enumerate(states)]
            result = detector(observations)
            if any(result[f] != int(r[f]) for f in ('surviving_sites','match_count','detected')):
                raise ValueError('source detector differs from frozen state row')
            rows.append(dict(task=task,language='python',scheme=scheme,attack=attack,severity=severity,
                payload_index=payload,source_sha256=identity,proof_admitted=True,
                evidence_kind='restricted-AST-erasure-not-program-execution',
                **{f:result[f] for f in ('surviving_sites','match_count','detected')}))
            if number % 4000 == 0: print(json.dumps(dict(processed=number,unique_sources=len(cache))),flush=True)
        summary.update(status='PASS', configurations=len(rows),
            distinct_task_source_identities=len(cache), source_detection_disagreements=0,
            source_semantic_admission='All Python rows satisfy the explicit erasure contract; not generic semantic verification',
            all_dense_program_semantics_executed=False, historical_executed_dense_links=432,
            historical_executed_unknown_labels=75600, new_program_executions=0,
            javascript_source_admission_added=False,
            per_scheme={s:dict(configurations=sum(r['scheme']==s for r in rows),
                detected=sum(r['detected'] for r in rows if r['scheme']==s)) for s in SCHEMES})
        with (out/'rows.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    except BaseException as exc:
        summary.update(error=dict(type=type(exc).__name__,message=str(exc)),completed=len(rows))
        raise
    finally:
        summary.update(input_sha256=inputs, source_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
            for name in ('check_source_admission.py','src/covewm/source_admission.py',
                         'src/covewm/benchmark.py','src/covewm/tasks.py')})
        (out/'summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
        (out/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),
            platform=platform.platform(),elapsed_seconds=time.monotonic()-start),indent=2)+'\n',encoding='utf-8')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,default=HERE/'results/current/results')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=run(a.results,a.out)
    print(json.dumps({k:r[k] for k in ('status','configurations','distinct_task_source_identities','source_detection_disagreements')}))
