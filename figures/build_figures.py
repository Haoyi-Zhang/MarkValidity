"""Regenerate the current architecture using the shared figure source."""
import argparse
from pathlib import Path

from figure_style import paper_style
from publication_figures import architecture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    paper_style('tosem')
    architecture(args.outdir, None)


if __name__ == '__main__':
    main()

