"""Schematic assumption checks for mixture and calibration."""
from diagram_ink import Diagram, S, T, A, G

def mixture_transport():
    d=Diagram(420,78)
    for center,c,label in [(67,T,r'Donor: largest $\Delta_j$'),
                            (353,A,r'Recipient: smallest $\Delta_j$')]:
        d.mark('store',center,47,29,c)
        d.txt(center,27,label,9.4,color=c)
    d.wire((94,47),(327,47),c=G,dash=True)
    d.txt(211,61,r'Transfer at most $\rho$ mixture mass',10.0)
    d.txt(211,11,r'Upper bound on decrease: $\rho(\max\Delta-\min\Delta)$',10.0)
    return d

def calibration_unit():
    d=Diagram(420,94)
    d.mark('doc',27,49,21,S)
    d.txt(35,20,'One null input',9.3,color=S)
    d.wire((42,49),(83,49),(83,69),(111,69),c=S)
    d.wire((83,49),(83,29),(111,29),c=S)
    for y,label in ((69,'First key / window'),(29,'Other keys / windows')):
        d.mark('keyed',124,y,18,S)
        d.txt(142,y,label,9.3,ha='left')
        d.wire((239,y),(285,y),(285,57 if y>49 else 41),c=T)
    d.diamond(285,49,7,T)
    d.txt(304,67,'Search rule',9.3,color=T,ha='left')
    d.wire((294,49),(337,49),c=T)
    d.mark('trace',354,49,19,T)
    d.txt(365,20,'One search outcome',9.3,color=T)
    return d

FIGURES={'mixture-transport':mixture_transport,'calibration-unit':calibration_unit}
