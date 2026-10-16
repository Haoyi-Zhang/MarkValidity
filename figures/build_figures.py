"""Direct vector schematic of the declared evaluation sequence."""
from pathlib import Path
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch

plt.rcParams.update({'font.family': 'STIXGeneral', 'mathtext.fontset': 'stix',
                     'font.size': 9, 'pdf.fonttype': 42, 'ps.fonttype': 42,
                     'text.usetex': False, 'axes.unicode_minus': False})


class Drawing:
    def __init__(self, width, height):
        self.fig = plt.figure(figsize=(width/2.54, height/2.54))
        self.ax = self.fig.add_axes([0, 0, 1, 1], xlim=(0, width), ylim=(0, height))
        self.ax.set_aspect('equal')
        self.ax.axis('off')
        self.labels = []

    def text(self, x, y, text, size=9, **kw):
        label = self.ax.text(x, y, text, ha='center', va='center',
                             fontsize=size, linespacing=1.15, zorder=4, **kw)
        self.labels.append(label)

    def box(self, x, y, width, height, text='', circle=False):
        patch = Circle((x, y), width/2) if circle else Rectangle((x-width/2, y-height/2), width, height)
        patch.set(edgecolor='black', facecolor='white', linewidth=.65, zorder=2)
        self.ax.add_patch(patch)
        if text:
            self.text(x, y, text)

    def line(self, points, arrow=False, dashed=False):
        xs, ys = zip(*points)
        self.ax.plot(xs, ys, color='black', lw=.65, linestyle='--' if dashed else '-', zorder=1)
        if arrow:
            self.ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle='-|>',
                             mutation_scale=8, lw=.65, color='black', zorder=1))

    def save(self, out, name):
        self.fig.canvas.draw()
        renderer = self.fig.canvas.get_renderer()
        extent = self.fig.bbox
        for label in self.labels:
            box = label.get_window_extent(renderer)
            if box.x0 < extent.x0 or box.x1 > extent.x1 or box.y0 < extent.y0 or box.y1 > extent.y1:
                raise ValueError('Clipped label: ' + label.get_text())
        self.fig.savefig(out/(name+'.pdf'), metadata={'Creator': 'Python Matplotlib',
                         'Producer': None, 'CreationDate': None, 'ModDate': None})
        plt.close(self.fig)

def architecture(out):
    d = Drawing(15.2, 6.7)
    coords = [(2.4, 5.1), (7.5, 5.1), (12.6, 5.1),
              (12.6, 2.8), (7.5, 2.8)]
    labels = ['1. Claim\nconstruct, unit,\nassumptions, falsifier',
              '2. Freeze\ntasks, interventions,\ndetector, mixtures',
              '3. Execute\nprogram pairs,\ncarriers, attacks',
              '4. Preserve\nfailures, strata,\nraw outcomes',
              '5. Interpret\nestimands, stress\ntests, scope']
    for (x, y), label in zip(coords, labels):
        d.box(x, y, 4.1, 1.65, label)
    for a, b in zip(coords, coords[1:]):
        if a[1] == b[1]:
            direction = 1 if b[0] > a[0] else -1
            d.line([(a[0]+2.05*direction, a[1]),
                    (b[0]-2.05*direction, b[1])], arrow=True)
        else:
            d.line([(a[0], a[1]-.825), (b[0], b[1]+.825)], arrow=True)
    d.text(3, 1.0, 'Preserved evidence:', 9)
    for x, label, color in [(6.0, 'semantic', '#0072B2'), (8.5, 'source', '#8A9098'),
                             (10.75, 'attack', '#4D5661'), (13.0, 'null', '#31536D')]:
        d.ax.plot([x-.8, x-.3], [1, 1], color=color, lw=1.2)
        d.text(x+.4, 1, label, 9)
    d.save(out, 'architecture')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--outdir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    architecture(args.outdir)


if __name__ == '__main__':
    main()

