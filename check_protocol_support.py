"""Recompute support-matched scoring sensitivity without executing programs."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'src'))
from covewm.external_replay import support_matched_discrimination


def run(results, out):
    results, out = Path(results).resolve(), Path(out).resolve()
    if out.exists() or out.is_relative_to(results) or results.is_relative_to(out):
        raise ValueError('fresh output disjoint from retained input required')
    manifest_rows = list(csv.DictReader((results / 'results_manifest.csv').open(encoding='utf-8', newline='')))
    manifest = {r['relative_path']: r for r in manifest_rows}
    if len(manifest) != len(manifest_rows):
        raise ValueError('duplicate manifest entry')
    data = (results / 'raw/robustness.csv').read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    entry = manifest['raw/robustness.csv']
    if entry['sha256'] != digest or int(entry['bytes']) != len(data):
        raise ValueError('retained input differs from manifest')
    report = support_matched_discrimination(list(csv.DictReader(io.StringIO(data.decode('utf-8')))))
    report['input_sha256'] = digest
    report['producer_sha256'] = {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__).resolve(), HERE / 'src/covewm/external_replay.py')}
    out.mkdir(parents=True)
    (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=HERE / 'results/current/results')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results, args.out), sort_keys=True))
