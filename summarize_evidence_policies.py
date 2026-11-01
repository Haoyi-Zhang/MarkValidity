"""Currently validate retained evidence policies, without executing task programs.

The Python proof policy is admitted by a fresh, bounded static AST-erasure check,
not by the unbound historical proof_admitted flag or an invented old receipt.
Historical rows, summaries, execution labels and research budgets are read-only.
"""
import argparse
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from covewm.benchmark import (ALPHA, ATTACKS, PAYLOAD_BITS, PAYLOAD_COUNT, SCHEMES,
    SEVERITIES, CarrierState, attacked_states, binomial_tail, detector,
    extract_carriers, payload_bits, render_program)
from covewm.source_admission import admit_python
from covewm.tasks import TASK_BY_NAME
from check_source_detection import analyze as analyze_source_detection

MAX_SOURCE_ADMISSIONS = 38016
WALL_LIMIT_SECONDS = 480
LANGUAGES = ('python', 'javascript')
SEVERITY_KEYS = tuple(f'{v:.1f}' for v in SEVERITIES)


def integer(row, field):
    value = row.get(field)
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError('missing or invalid integer: ' + field)
    number = int(value)
    if str(number) != value:
        raise ValueError('noncanonical integer: ' + field)
    return number


def key(row):
    severity = row.get('severity')
    if severity not in SEVERITY_KEYS:
        raise ValueError('invalid severity key')
    attack = row.get('attack', row.get('condition'))
    if 'attack' in row and 'condition' in row and row['attack'] != row['condition']:
        raise ValueError('conflicting attack and condition')
    return (row['task'], row['language'], row['scheme'], attack,
            severity, integer(row, 'payload_index'))


def audit_key(row):
    return row['task'], row['language'], row['scheme'], row['condition']


def expected_keys():
    return set(itertools.product(TASK_BY_NAME, LANGUAGES, SCHEMES, ATTACKS,
                                 SEVERITY_KEYS, range(PAYLOAD_COUNT)))


def indexed(rows, key_function, expected, label):
    result = {}
    for row in rows:
        try:
            k = key_function(row)
        except (KeyError, TypeError) as exc:
            raise ValueError(label + ' schema mismatch') from exc
        if k in result:
            raise ValueError(label + ' duplicate key')
        result[k] = row
    if set(result) != expected:
        raise ValueError(label + ' exact key coverage mismatch')
    return result


def source_identity(row):
    digest = row.get('source_sha256')
    if (not isinstance(digest, str) or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest)):
        raise ValueError('missing or invalid source_sha256')
    return digest


def detection_counts(row):
    n, m, d = (integer(row, f) for f in ('surviving_sites', 'match_count', 'detected'))
    if not 0 <= m <= n <= PAYLOAD_BITS or d not in (0, 1):
        raise ValueError('invalid detector counts')
    if d != int(binomial_tail(n, m) <= ALPHA):
        raise ValueError('detector decision disagrees with counts')
    return n, m, d


def check_deadline(started):
    if time.monotonic() - started >= WALL_LIMIT_SECONDS:
        raise TimeoutError('current static validation exceeded 480-second limit')


def validate_executions(rows, dense, fresh_rows):
    """Use the actual manifest-bound semantic/source bridge, not reported flags.

    The bridge re-renders the 504 historical sources, requires their identities
    in successful retained semantic audits, and extracts actual detector inputs.
    Its 72 carrier-only controls are checked but stay outside the dense universe.
    """
    expected = set(itertools.product(TASK_BY_NAME, LANGUAGES, SCHEMES,
                                     ('carrier_only',) + ATTACKS))
    archived = indexed(rows, audit_key, expected, 'executed source inventory')
    fresh = indexed(fresh_rows, audit_key, expected, 'reconstructed source inventory')
    executions = {}
    for k, row in archived.items():
        actual = fresh[k]
        linked = k[3] != 'carrier_only'
        if integer(row, 'payload_index') != 0 or row.get('severity') != ('1.0' if linked else ''):
            raise ValueError('executed source configuration mismatch')
        if source_identity(row) != source_identity(actual):
            raise ValueError('executed source identity disagrees with retained semantic audit')
        for field in ('retained_semantic_label', 'source_identity_matches_retained_audit', 'dense_linked'):
            if actual.get(field) is not (linked if field == 'dense_linked' else True):
                raise ValueError('reconstructed semantic/source premise failed')
            if row.get(field) != str(actual[field]):
                raise ValueError('executed source evidence flag mismatch')
        counts = detection_counts(row)
        if counts != tuple(actual[f] for f in ('surviving_sites', 'match_count', 'detected')):
            raise ValueError('executed source detection mismatch')
        for field in ('realized_bit_changes', 'deletions'):
            if integer(row, field) != actual[field]:
                raise ValueError('executed source operation accounting mismatch')
        for field in ('p_value', 'match_rate'):
            try:
                value = float(row[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError('invalid executed source statistic: ' + field) from exc
            if not math.isfinite(value) or not math.isclose(value, actual[field], rel_tol=0, abs_tol=1e-15):
                raise ValueError('executed source statistic mismatch: ' + field)
        if linked:
            dense_key = key(row)
            if counts != detection_counts(dense[dense_key]):
                raise ValueError('executed source disagrees with dense detection')
            executions[dense_key] = source_identity(row), counts
    expected_links = {k for k in expected_keys() if k[4] == '1.0' and k[5] == 0}
    if set(executions) != expected_links:
        raise ValueError('executed dense-link exact key coverage mismatch')
    return executions


def validate_proofs(rows, dense, started):
    """Re-admit the frozen Python sources now; never execute their task bodies."""
    expected = {k for k in expected_keys() if k[1] == 'python'}
    records = indexed(rows, key, expected, 'Python proof inventory')
    cache, proofs = {}, {}
    for k, row in sorted(records.items()):
        check_deadline(started)
        if (row.get('proof_admitted') != 'True'
                or row.get('evidence_kind') != 'restricted-AST-erasure-not-program-execution'):
            raise ValueError('historical proof record schema mismatch')
        counts = detection_counts(row)
        if counts != detection_counts(dense[k]):
            raise ValueError('proof record disagrees with dense detection')
        task, language, scheme, attack, severity, payload = k
        bits = payload_bits(task, language, payload)
        states, _ = attacked_states(bits, scheme, attack, float(severity), task, language, payload)
        source = render_program(TASK_BY_NAME[task].python_reference, language, states,
                                formatted=attack == 'format')
        identity = hashlib.sha256(source.encode('utf-8')).hexdigest()
        if source_identity(row) != identity:
            raise ValueError('proof source identity disagrees with reconstructed source')
        # Cache only an exactly identical task/source pair, local to this call.
        cache_key = task, source
        if cache_key not in cache:
            if len(cache) >= MAX_SOURCE_ADMISSIONS:
                raise ValueError('current static validation source-admission limit exceeded')
            admitted = admit_python(task, source)
            check_deadline(started)
            if admitted.get('admitted') is not True:
                raise ValueError('current AST-erasure admission failed')
            cache[cache_key] = admitted['observed']
        actual = cache[cache_key]
        if (actual != {s.index: s.observed for s in states if s.present}
                or actual != extract_carriers(source, language)):
            raise ValueError('current AST/source/state observations disagree')
        observations = [CarrierState(s.index, s.channel, s.expected, actual.get(s.index, 0),
                                    s.index in actual, 'current-AST-erasure') for s in states]
        decision = detector(observations)
        if counts != tuple(decision[f] for f in ('surviving_sites', 'match_count', 'detected')):
            raise ValueError('proof record disagrees with current source detection')
        proofs[k] = identity, counts
    check_deadline(started)
    return proofs, len(cache)


def check_overlap(proofs, executions):
    # Both source identity and all three detector counts must agree.
    if any(executions[k] != proofs[k] for k in set(executions) & set(proofs)):
        raise ValueError('proof/execution source identity or detection overlap disagrees')


def summarize():
    started = time.monotonic()
    inputs = ['results/raw/robustness.csv', 'results/source_admission/rows.csv.gz',
              'results/source_detection/rows.csv']
    data = {name: (ROOT / name).read_bytes() for name in inputs}
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in data.items()}
    def table(value):
        return list(csv.DictReader(io.StringIO(value.decode('utf-8'))))
    dense = indexed(table(data[inputs[0]]), key, expected_keys(), 'dense inventory')
    for row in dense.values():
        detection_counts(row)
    # Reuse the existing nonexecuting bridge. It verifies the retained manifest,
    # successful semantic premises, actual source hashes and actual extraction.
    fresh, _, bridge = analyze_source_detection(ROOT / 'results')
    if bridge['input_sha256']['raw/robustness.csv'] != hashes[inputs[0]]:
        raise ValueError('source bridge and policy consumed different dense inputs')
    hashes.update({'results/' + name: digest for name, digest in bridge['input_sha256'].items()})
    check_deadline(started)
    executions = validate_executions(table(data[inputs[2]]), dense, fresh)
    proofs, distinct_sources = validate_proofs(table(gzip.decompress(data[inputs[1]])), dense, started)
    check_overlap(proofs, executions)
    javascript = {k: v for k, v in executions.items() if k[1] == 'javascript'}
    def interval(values):
        known, positive = len(values), sum(v[1][2] for v in values.values())
        return dict(universe=len(dense), known=known, unknown=len(dense)-known,
                    detected=positive, lower_numerator=positive,
                    upper_numerator=positive+len(dense)-known, denominator=len(dense))
    joint = dict(proofs)
    joint.update(javascript)
    sources = ('summarize_evidence_policies.py', 'check_source_detection.py',
               'src/covewm/benchmark.py', 'src/covewm/source_admission.py', 'src/covewm/tasks.py')
    source_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    check_deadline(started)
    return dict(status='PASS', historical_labels_changed=False, task_programs_executed=0,
        execution_only=interval(executions), proof_supported=interval(joint),
        proof_admitted_python_detected=sum(v[1][2] for v in proofs.values()),
        executed_javascript_detected=sum(v[1][2] for v in javascript.values()),
        premise='Current restricted Python AST-erasure revalidation plus retained source-identity-bound execution labels; no generic equivalence or new execution claim',
        validation_scope=dict(kind='current-deterministic-static-revalidation',
            validated_at_utc=datetime.now(timezone.utc).isoformat(),
            proof_configurations_revalidated=len(proofs), distinct_task_source_admissions=distinct_sources,
            maximum_source_admissions=MAX_SOURCE_ADMISSIONS, wall_limit_seconds=WALL_LIMIT_SECONDS,
            historical_success_receipt_restored=False, historical_research_budgets_changed=False,
            upstream_programs_executed=0, model_API_calls=0,
            executed_dense_links_source_bound=len(executions),
            carrier_only_controls_checked=len(fresh)-len(executions)),
        input_bindings=hashes, validator_source_sha256=source_hashes)

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
