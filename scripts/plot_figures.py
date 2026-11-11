#!/usr/bin/env python3
"""Render quantitative vector figures from retained data without experiments."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "figures"))
from figure_style import paper_style

def configure_fonts(font_dir: Path | None = None) -> str:
    """Resolve the exact body face used by the compiled ACM manuscript."""
    from matplotlib import font_manager
    family = paper_style(font_dir=font_dir)
    matplotlib.rcParams.update({
        "font.family": family, "font.size": 8.5,
        "pdf.use14corefonts": False,
        "text.usetex": False, "mathtext.fontset": "custom",
        "mathtext.rm": family, "mathtext.it": family + ":italic",
        "mathtext.bf": family, "mathtext.sf": family, "mathtext.tt": family,
        "mathtext.cal": "Libertinus Math", "mathtext.fallback": "stix",
        "axes.unicode_minus": True, "axes.linewidth": 0.55,
        "xtick.major.width": 0.45, "ytick.major.width": 0.45,
        "xtick.major.size": 3, "ytick.major.size": 3,
    })
    resolved = font_manager.findfont(
        font_manager.FontProperties(family=family), fallback_to_default=False)
    print("FIGURE_FONT", resolved)
    return family

NAVY, TEAL, AMBER, SLATE = "#265776", "#176a61", "#9b481e", "#485461"


def make_figure(width: float, height: float, box: tuple):
    fig = plt.figure(figsize=(width / 72, height / 72))
    x, y, w, h = box
    ax = fig.add_axes([x / width, y / height, w / width, h / height])
    ax.tick_params(direction="in", pad=3, labelsize=9.0, colors=SLATE)
    for spine in ax.spines.values():
        spine.set_color("#717882")
    return fig, ax


def gate_geometry():
    # Preserve the square 195.07 bp plot and its closed acceptance rectangle.
    fig, ax = make_figure(229, 223, (32, 27, 195.07, 195.07))
    ax.set(xlim=(0.58, 1.02), ylim=(0.58, 1.02), aspect="equal")
    ticks = [0.6, 0.7, 0.8, 0.9, 1.0]
    ax.set_xticks(ticks, ["0.6", "0.7", "0.8", "0.9", "1"])
    ax.set_yticks(ticks, ["0.6", "0.7", "0.8", "0.9", "1"])
    ax.tick_params(top=True, right=True)
    ax.grid(axis="y", color="#e6e6e6", linewidth=0.3)
    ax.set_axisbelow(True)
    tint = tuple(0.13 * v + 0.87 for v in matplotlib.colors.to_rgb(TEAL))
    ax.add_patch(Rectangle((0.8, 0.8), 0.2, 0.2, color=tint, linewidth=0, zorder=1))
    ax.plot([0.64, 1.0], [1.0, 0.64], color=SLATE,
            linestyle=(0, (1, 1.6)), linewidth=0.75, label="Equal-score lines")
    ax.plot([0.70, 1.0], [1.0, 0.70], color=AMBER,
            linestyle=(0, (1, 1.5)), linewidth=0.7)
    ax.plot([0.8, 0.8], [0.58, 1.0], color="#717882",
            linestyle=(0, (4.2, 2)), linewidth=0.65, label="Gate thresholds")
    ax.plot([0.58, 1.0], [0.8, 0.8], color="#717882",
            linestyle=(0, (4.2, 2)), linewidth=0.65)
    ax.plot([0.82], [0.82], "o", color=TEAL, markersize=4.2)
    ax.plot([1.0], [0.70], "^", color=AMBER, markersize=4.8)
    ax.text(0.81, 0.955, "gate satisfied", ha="left", va="bottom",
            color="#363c44", fontsize=8.47)
    ax.text(0.825, 0.825, "$A$", ha="left", va="bottom", color=TEAL, fontsize=8.47)
    ax.text(0.995, 0.695, "$B$", ha="right", va="top", color=AMBER, fontsize=8.47)
    ax.legend(loc="lower left", bbox_to_anchor=(0.03, 0.065), frameon=False,
              borderaxespad=0, handlelength=2.2, handletextpad=.5,
              labelspacing=.43, fontsize=8.3)
    ax.set_xlabel(r"Executable-semantic score $x_1$", fontsize=9.0, labelpad=2)
    ax.set_ylabel(r"Calibration score $x_2$", fontsize=9.0, labelpad=2)
    return fig


def metric_fingerprint():
    rows = np.loadtxt(ROOT / "figure_data/intervention-heatmap.dat", skiprows=1)
    if rows.shape != (36, 3) or len({(x, y) for x, y, _ in rows}) != 36:
        raise ValueError("Expected the retained 9-by-4 coefficient grid")
    values = np.empty((9, 4))
    for x, y, value in rows:
        if x != int(x) or y != int(y) or not (1 <= x <= 4 and 1 <= y <= 9):
            raise ValueError("Invalid heatmap cell")
        values[int(y) - 1, int(x) - 1] = value
    # The long normalization label needs its own gutter at print size.
    fig, ax = make_figure(425, 255, (96, 51, 327, 201))
    cmap = LinearSegmentedColormap.from_list("cove diverging", ["#163953", "white", AMBER])
    # pcolormesh and the colorbar remain vector, not imshow/rasterized meshes.
    mesh = ax.pcolormesh(np.arange(0.5, 5.5), np.arange(0.5, 10.5), values,
                         cmap=cmap, vmin=-1, vmax=1, shading="flat",
                         rasterized=False, edgecolors="face", linewidth=0)
    ax.set(xlim=(0.5, 4.5), ylim=(0.5, 9.5))
    ax.set_xticks(range(1, 5), ["Format", "Identifier", "Structure", "Delete"])
    ax.set_yticks(range(1, 10), [
        "Payload match", "Carrier retention", "Identifier style", "Identifier multiset",
        "Control profile", "AST type", "ID/number-normalized", "Token", "Character",
    ])
    ax.tick_params(length=0, colors="black", pad=3)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for x, y, value in rows:
        label = f"{value:.2f}".rstrip("0").rstrip(".")
        if label == "-0":
            label = "0"
        # Choose the stronger foreground for the actual mapped cell color.
        # The sRGB relative-luminance calculation leaves the mesh itself intact.
        rgb = cmap(mesh.norm(value))[:3]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055)**2.4 for c in rgb]
        lum = sum(w*c for w,c in zip((.2126,.7152,.0722),linear))
        contrast = ((lum + .05) / .05, 1.05 / (lum + .05))
        assert max(contrast) >= 4.5
        ax.text(x, y, label, ha="center", va="center", fontsize=9.2,
                color="white" if contrast[1] > contrast[0] else "black")
    cax = fig.add_axes([134.4 / 425, 27 / 255, 239.9 / 425, 6.24 / 255])
    cb = fig.colorbar(mesh, cax=cax, orientation="horizontal",
                      ticks=[-1, -0.5, 0, 0.5, 1])
    # Explicit opaque PDF paths stay vector even in readers that rasterize
    # the default colorbar mesh. Overlap neighboring bands so the viewer
    # never blends a band edge against a white background.
    cb.solids.set_visible(False)
    edges = np.linspace(-1, 1, 129)
    for lo, hi in zip(edges[:-1], edges[1:]):
        cax.add_patch(Rectangle((lo, 0), hi-lo+.013, 1,
                                facecolor=cmap(mesh.norm((lo+hi)/2)), linewidth=0))
    cb.ax.tick_params(length=0, pad=3, labelsize=9.0)
    cb.set_label(r"Standardized intervention coefficient $\beta$", fontsize=9.0, labelpad=2)
    return fig


def mixture_frontier():
    rows = np.genfromtxt(ROOT / "figure_data/mixture-frontier.dat", names=True)
    if len(rows) != 101 or not np.allclose(rows["rename_share"], np.arange(101) / 100,
                                         rtol=0, atol=1e-12):
        raise ValueError("Expected the retained 101-point frontier")
    fig, ax = make_figure(383, 195, (31, 25, 349.30, 152.23))
    for field, label, color, dash, marker, size in [
        ("lexical", "Lexical", NAVY, "-", "o", 3.1),
        ("structural", "Structural", AMBER, "--", "s", 2.9),
        ("hybrid", "Hybrid", TEAL, "-.", "^", 3.5),
    ]:
        ax.plot(rows["rename_share"], rows[field], label=label, color=color,
                linestyle=dash, linewidth=0.8, marker=marker,
                markersize=size, markevery=(8+4*len(ax.lines),20), markeredgewidth=0.60,
                markerfacecolor="white")
    ax.plot([0.500919, 0.500919], [0.20, 0.72], color=SLATE,
            linestyle=(0, (3, 1.5)), linewidth=0.55)
    # This symbol uses the same math font as the paper.
    ax.text(0.54, 0.69, r"$t^{\mathcal{\star}}=0.500919$", ha="left", va="top",
            fontsize=8.47, color=SLATE,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    ax.set(xlim=(0, 1), ylim=(0.20, 0.72))
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0", "0.25", "0.5", "0.75", "1"])
    ax.set_yticks(np.arange(0.2, 0.71, 0.1))
    ax.grid(axis="y", color="#e6e6e6", linewidth=0.3)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlabel(r"Rename share $t$ of targeted mass", fontsize=9.1, labelpad=2)
    ax.set_ylabel("Mixture score", fontsize=9.1, labelpad=2)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.017),
              frameon=False, borderaxespad=0, fontsize=8.47,
              handlelength=2, handletextpad=0.65, columnspacing=1.5)
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-dir", type=Path)
    parser.add_argument("--outdir", type=Path)
    parser.add_argument("--only", choices=("gate-geometry", "metric-fingerprint", "mixture-frontier"))
    args = parser.parse_args()
    configure_fonts(args.font_dir)
    output = args.outdir or ROOT / "figures"
    paper = ROOT.parent / "paper/figures"
    output.mkdir(parents=True, exist_ok=True)
    if args.outdir is None and paper.parent.is_dir():
        paper.mkdir(parents=True, exist_ok=True)
    for name, producer in [
        ("gate-geometry", gate_geometry),
        ("metric-fingerprint", metric_fingerprint),
        ("mixture-frontier", mixture_frontier),
    ]:
        if args.only and name != args.only:
            continue
        fig = producer()
        path = output / f"{name}.pdf"
        fig.savefig(path, metadata={"Creator": None, "Producer": None,
                                    "CreationDate": None, "ModDate": None})
        plt.close(fig)
        if args.outdir is None and paper.is_dir():
            shutil.copyfile(path, paper / path.name)
        print("FIGURE_OK", path)


if __name__ == "__main__":
    main()
