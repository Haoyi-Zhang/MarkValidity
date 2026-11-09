"""Rebuild the paper's mechanism schematics at their intended physical size."""
from pathlib import Path
from diagram_core import Figure, BLUE, GRAY, INK, RED

def below(f,x,y,icon,label):
    """Keep multiline labels clear of the glyph at actual print scale."""
    f.icon(icon,x,y)
    f.t(x,y+f.units(19.5)[1],label)

def project_transfer(f):
    f.node(43,48,'source','Frozen modules')
    f.route((57,48),(92,48))
    f.line((92,17),(92,79),color=BLUE,check=True)
    for y, icon, label in [(17,'trace','Trailing comment'),(48,'diff','Scoped parameter rename'),(79,'reject','Scope-blind collapse')]:
        f.route((92,y),(117,y),color=RED if y==79 else BLUE)
        f.node(132,y,icon,label,side='right',color=RED if y==79 else BLUE)
        f.route((258,y),(285,y),color=RED if y==79 else BLUE)
    f.line((285,17),(285,79),color=BLUE,check=True)
    f.route((285,48),(310,48))
    f.node(326,48,'check','Parse + compile')
    f.t(413,83,'No runtime claim',align='right',color=GRAY,style='italic')

def claim_gate(f):
    for x, icon, label in [(49,'run','Executable\nsemantics'),(150,'filter','Null\ncalibration'),(268,'grid','Declared\nattack mixture'),(371,'compare','Conditional\ncomparison')]:
        below(f,x,36,icon,label)
    for a,b in [(64,136),(165,253),(283,356)]:
        f.route((a,36),(b,36))
    f.route((49,23),(49,13),(149,13),dash=True,color=RED)
    f.line((150,23),(150,13),dash=True,color=RED,check=True)
    f.t(163,13,'Failed gate: no comparison',align='left',color=RED)
    f.line((96,84),(137,84),color=GRAY,weight=.78)
    f.t(145,84,'required check',align='left',color=GRAY)
    f.line((244,84),(282,84),color=RED,dash=True,weight=.78)
    f.t(290,84,'stop condition',align='left',color=GRAY)

FIGURES = [('project_transfer', 420, 90), ('claim_gate', 420, 79)]

if __name__ == '__main__':
    for name,w,h in FIGURES:
        f=Figure(dict(media=(w,h),trim=(0,0,0,0),width=w))
        globals()[name](f)
        f.finish(Path(__file__).parent/(name.replace('_','-')+'.pdf'))
