# Figure reproduction

The evaluation architecture, attack-response panels, transfer panels and
nominal-survival plot are generated directly by Python:

```sh
python -m pip install matplotlib==3.11.2
python -B figures/publication_figures.py
```

The response and transfer panels read the retained arrays in `data/`; the
survival panel reads the 72 retained mutant outcomes. The paper build copies
the generated PDFs verbatim. None of these commands executes an experiment.

From the artifact directory, run:

```sh
python scripts/plot_figures.py
```

Plotting requires Matplotlib (with its NumPy dependency); it does not require
TeX or the scientific experiment dependencies. The gate plot uses the stated threshold geometry. The heatmap and frontier read exact copies of the retained paper tables in `figure_data/`; coefficients are not refitted, and the 101 frontier points are not new trials.

The native outputs are the PDFs in this directory. When the sibling paper
directory is present, the producer copies identical PDF bytes into its figures
directory. The figure PDFs are vector artwork; captions and references are
typeset separately in the manuscript.

The figure labels use Linux Libertine O, the same family embedded in the paper.
The original OpenType faces are resolved through `kpsewhich` or
`FIGURE_TEX_FONT_DIR`. The bundled Libertine TrueType files are unchanged and are redistributed
under the SIL Open Font License in `../fonts/OFL-1.1.txt`. The upstream archive is
[Linux Libertine 5.3.0](https://sourceforge.net/projects/linuxlibertine/files/linuxlibertine/5.3.0/LinLibertineTTF_5.3.0_2012_07_02.tgz/download);
the downloaded archive matched its published SHA-256
`24a593a949808d976850131a953c0c0d7a72299531dfbb348191964cc038d75d`.
The source font files are unchanged.

The quantitative renderer also accepts `--font-dir DIRECTORY` for the original
OpenType faces. PDFs embed vector font subsets without invoking TeX to draw.

The mixture-frontier star uses the manuscript's Libertinus Math face.
The heatmap cells and colorbar are both vector
meshes, with rasterization explicitly disabled.
