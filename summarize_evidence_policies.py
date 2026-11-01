"""Recount retained executed and proof-admitted evidence without executing tasks.

These are separate evidence policies, not rewritten historical semantic labels.
The proof-supported policy is conditional on the restricted AST-erasure argument.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def key(row):
    return (row['task'], row['language'], row['scheme'], row.get('attack', row.get('condition')),
            str(float(row['severity'])), int(row['payload_index']))

def summarize():
    inputs = ['results/raw/robustness.csv', 'results/source_admission/rows.csv.gz',
              'results/source_detection/rows.csv']
    with (ROOT / inputs[0]).open(encoding='utf-8', newline='') as stream:
        raw = list(csv.DictReader(stream))
    dense = {key(r): r for r in raw}
    if len(raw) != 76032 or len(dense) != len(raw):
        raise ValueError('complete unique dense universe required')
    with gzip.open(ROOT / inputs[1], 'rt', encoding='utf-8', newline='') as stream:
        proof = list(csv.DictReader(stream))
    with (ROOT / inputs[2]).open(encoding='utf-8', newline='') as stream:
        observed = [r for r in csv.DictReader(stream) if r['dense_linked'] == 'True']
    proofs = {}
    for row in proof:
        k = key(row)
        if (row['language'] != 'python' or row['proof_admitted'] != 'True'
                or k not in dense or k in proofs or row['detected'] != dense[k]['detected']):
            raise ValueError('invalid or duplicate proof-supported source link')
        proofs[k] = int(row['detected'])
    executions = {}
    for row in observed:
        k = key(row)
        if (k not in dense or k in executions or row['retained_semantic_label'] != 'True'
                or row['source_identity_matches_retained_audit'] != 'True'
                or row['detected'] != dense[k]['detected']):
            raise ValueError('invalid or duplicate executed source link')
        executions[k] = int(row['detected'])
    if len(proofs) != 38016 or len(executions) != 432:
        raise ValueError('unexpected policy denominators')
    javascript = {k: v for k, v in executions.items() if k[1] == 'javascript'}
    overlap = set(executions) & set(proofs)
    if len(javascript) != 216 or any(executions[k] != proofs[k] for k in overlap):
        raise ValueError('evidence overlap disagrees')
    def interval(values):
        known, positive = len(values), sum(values.values())
        return dict(universe=len(dense), known=known, unknown=len(dense)-known,
                    detected=positive, lower_numerator=positive,
                    upper_numerator=positive+len(dense)-known, denominator=len(dense))
    joint = dict(proofs)
    joint.update(javascript)
    return dict(status='PASS', historical_labels_changed=False, task_programs_executed=0,
        execution_only=interval(executions), proof_supported=interval(joint),
        proof_admitted_python_detected=sum(proofs.values()), executed_javascript_detected=sum(javascript.values()),
        premise='Restricted Python AST-erasure soundness plus retained source-identity-bound execution labels; no generic equivalence or execution claim',
        input_bindings={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs})

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=summarize()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
