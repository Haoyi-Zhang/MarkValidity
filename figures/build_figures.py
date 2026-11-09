"""Render the four independent measurement routes."""
import argparse
from pathlib import Path

def architecture(out):
    from mark_panels import architecture as panel
    return panel(out / "architecture.pdf")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--outdir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    architecture(args.outdir)


if __name__ == '__main__':
    main()
