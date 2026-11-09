"""Regenerate the paper's mechanism figures."""
import argparse
import json
from pathlib import Path
from article_diagrams import FIGURES
from diagram_ink import emit
from figure_style import paper_style
from figure_style import Plate, BLUE, TEAL, LIGHT, MINT
from matplotlib.transforms import Bbox

COLORS={'blue':(BLUE,LIGHT),'teal':(TEAL,MINT)}


def check_labels(d, placed, arrows):
    """Verify labels against reserved space and every horizontal or vertical route."""
    d.fig.canvas.draw()
    render=d.fig.canvas.get_renderer()
    tf=d.ax.transData
    canvas=d.fig.bbox
    boxes=[]
    for text,reserved in placed:
        box=text.get_window_extent(render)
        (x0,y0),(x1,y1)=tf.transform(((reserved[0],reserved[1]),(reserved[2],reserved[3])))
        assert box.x0>=x0-.5 and box.x1<=x1+.5 and box.y0>=y0-.5 and box.y1<=y1+.5, text.get_text()
        assert canvas.contains(box.x0,box.y0) and canvas.contains(box.x1,box.y1),text.get_text()
        assert not any(box.overlaps(other) for other in boxes),text.get_text()
        for (a,b) in arrows:
            (ax,ay),(bx,by)=tf.transform((a,b))
            rect=Bbox.from_extents(min(ax,bx)-1.5,min(ay,by)-1.5,max(ax,bx)+1.5,max(ay,by)+1.5)
            assert not box.overlaps(rect),(text.get_text(),a,b)
        boxes.append(box)


def strata(spec,out,previews):
    width=spec.get('width',420)
    labels=[]
    arrows=[]
    d=Plate(width,74)
    for x, title, parts in ((9,'Equal stratum weights',(1,1)),(220,'Row weights',(2,1))):
        labels.append((d.text(x+94,61,title,9.6,weight='bold'),(x,53,x+188,70)))
        total=sum(parts)
        cursor=x
        for k,n in enumerate(parts):
            bar=188*n/total
            tone,fill=COLORS[['blue','teal'][k]]
            d.frame(cursor,10,bar,31,fill=fill,edge=tone)
            labels.append((d.text(cursor+bar/2,25,f'{chr(65+k)}  {n}/{total}',10.1,color=tone),
                           (cursor+4,13,cursor+bar-4,38)))
            cursor+=bar
    check_labels(d,labels,arrows)
    d.save(out,spec['name'],previews)


def draw(spec,out,previews=None):
    name=spec['name']
    if name in FIGURES:
        return emit(name,out,previews)
    if name=='stratum-weights':
        return strata(spec,out,previews)
    raise ValueError(name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--previews',type=Path)
    args=parser.parse_args()
    spec=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
    paper_style(spec['venue'])
    for item in spec['figures']:
        draw(item,args.output,args.previews)


if __name__=='__main__':
    main()
