"""Build the vector diagram used in the main manuscript."""
from pathlib import Path
from visual_grammar import Diagram, BLUE, RED, INK, MUTED, PALE, WARM, GRID

def draw(out):
    d=Diagram(w=408,h=104)
    d.title(14,91,'A','Nominal tests')
    d.title(220,91,'B','Declared finite domain')
    for x in (20,43,66,89,112):
        d.dot(x,59,4.2,BLUE,'white')
    d.text(15,34,'Reference and mutant agree on the suite',9.2,INK,'left')
    d.arrow((153,58),(201,58),c=MUTED)
    d.rect(221,44,171,29,PALE,GRID,.65)
    for x in (236,259,282,305,328):
        d.dot(x,59,4.2,BLUE,'white')
    d.cross(365,59,RED,4)
    d.text(221,29,'Year 1200: reference true, mutant false',9.2,RED,'left')
    d.dot(20,10,3.3,BLUE,'white')
    d.text(30,10,'Agreement',8.8,MUTED,'left')
    d.cross(227,10,RED,2.7)
    d.text(236,10,'Disagreement',8.8,MUTED,'left')
    d.finish(out)

if __name__ == '__main__':
    draw(Path(__file__).with_name('oracle-gap.pdf'))
