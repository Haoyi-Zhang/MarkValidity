"""Render measured attack-response traces."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "artifact/figures"))

HERE=Path(__file__).resolve().parent


def render(output=HERE/'attack-response.pdf',reader=None):
    from mark_panels import attack
    if reader is None:
        from draw_evaluation import read_checked
        reader=lambda path:read_checked('figdata/'+path)
    return attack(output,reader)
