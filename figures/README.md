# Figure reproduction

The architecture schematic connects the four retained observation streams to the
claims each can support:

```sh
python -m pip install matplotlib==3.11.2
python -B figures/build_figures.py
```

The manuscript architecture illustration is a fixed input under
`../paper/figures/illustrations/`. The reference schematic producer does not
overwrite it. Neither adds observations or numerical results.

From the artifact directory, run:

```sh
python scripts/plot_figures.py
```

Plotting requires Matplotlib (with its NumPy dependency); it does not require
TeX or the scientific experiment dependencies. The gate plot uses the stated threshold geometry. The heatmap and frontier read exact copies of the retained paper tables in `figure_data/`; coefficients are not refitted, and the 101 frontier points are not new trials.

The native outputs are the PDFs in this directory. When the sibling paper
directory is present, the producer copies identical PDF bytes into its figures
directory. Fixed PDF boxes retain the prior layout; no tight-crop rescaling or
rasterized data/text is used. The manuscript captions and references stay in TeX.

Figure labels embed Linux Libertine, the manuscript's body family. The
unchanged TrueType faces and their SIL Open Font License are in `../fonts/`.
The ACM template uses the corresponding Linux Libertine Type 1 faces.
The heatmap and color scale are vector, without TeX or rasterization.
