"""Schematic assumption checks for mixture and calibration."""
from diagram_ink import Diagram, S, T, A, G

def mixture_transport():
    d=Diagram(420,78)
    d.dotmark(67,48,5,c=T,fill=T)
    d.dotmark(353,48,5,c=A,fill=A)
    d.wire((80,48),(339,48),c=G,dash=True)
    d.txt(211,63,r'move at most $\rho$ mixture mass',10.0)
    d.txt(67,28,r'largest $\Delta_j$',9.8,color=T,bold=True)
    d.txt(353,28,r'smallest $\Delta_j$',9.8,color=A,bold=True)
    d.txt(211,11,r'Maximum decrease: $\rho(\max\Delta-\min\Delta)$',10.0)
    return d

def calibration_unit():
    d=Diagram(420,94)
    d.mark('doc',27,49,23,S)
    d.txt(36,19,'One null input',9.2,color=S,bold=True)
    d.wire((44,49),(84,49),(84,69),(119,69),c=S)
    d.wire((84,49),(84,29),(119,29),c=S)
    d.txt(131,69,'Key / window 1',9.7,ha='left')
    d.txt(131,29,'Other searched keys / windows',9.7,ha='left')
    d.wire((218,69),(295,69),(295,57),c=T)
    d.wire((277,29),(295,29),(295,41),c=T)
    d.diamond(295,49,7,T)
    d.wire((305,49),(337,49),c=T)
    d.mark('trace',354,49,20,T)
    d.txt(365,16,'One search outcome',9.7,color=T,bold=True)
    return d

FIGURES={'mixture-transport':mixture_transport,'calibration-unit':calibration_unit}
