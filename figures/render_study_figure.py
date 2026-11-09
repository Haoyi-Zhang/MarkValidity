"""Render the canonical architecture figure."""
import argparse
from pathlib import Path

def render(output):
    from mark_panels import architecture as panel
    return panel(output)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'paper/figures/architecture.pdf')
    a=p.parse_args()
    render(a.output)
