"""Schematic assumption checks for mixture and calibration."""
from diagram_ink import Diagram, S, T, A, G, F
from matplotlib.patches import FancyBboxPatch

def mixture_transport():
    d=Diagram(420,78)
    d.txt(90,66,r'Largest $\Delta_j$',9.6,color=T)
    d.txt(314,66,r'Smallest $\Delta_j$',9.6,color=A)
    d.block(58,35,64,18,T,'white')
    d.block(283,35,64,18,A,'white')
    d.node_label(90,44,r'$-\rho$',10,color=T)
    d.node_label(315,44,r'$+\rho$',10,color=A)
    d.wire((127,44),(275,44),c=G,dash=True)
    d.txt(203,55,'Mixture mass',9.2)
    d.wire((58,26),(58,22),(347,22),(347,26),c=G,arrow=False)
    d.txt(203,10,r'Decrease at most $\rho(\max\Delta-\min\Delta)$',9.7,color=G)
    return d

def calibration_unit():
    d=Diagram(420,94)
    d.mark('doc',35,47,22,S)
    d.txt(35,23,r'Null input $x$',9.2,color=S)
    d.wire((49,47),(77,47),c=S,arrow=False)
    d.dotmark(77,47,1.9,c=S,fill=S)
    for y,k in ((69,'1'),(47,'2'),(25,'m')):
        d.wire((80,47),(106,y),(124,y),c=S)
        d.dotmark(139,y,9,c=S)
        d.node_label(139,y,rf'$s_{k}$',9.5,color=S)
        d.wire((150,y),(179,y),(208,47),c=S,arrow=False)
    d.txt(139,86,'Candidate scores',9.2)
    d.dotmark(208,47,1.8,c=T,fill=T)
    d.wire((212,47),(234,47),c=T)
    d.diamond(245,47,6,T)
    d.txt(245,66,'Full search rule',9.3,color=T)
    d.txt(348,69,'One counted decision',9.0,color=T)
    d.wire((254,47),(297,47),c=T)
    d.ax.add_patch(FancyBboxPatch((300,37),95,20,boxstyle='round,pad=0,rounding_size=3.5',
                  linewidth=.74,edgecolor=T,facecolor='white',zorder=3))
    d.mark('trace',315,47,15,T)
    d.node_label(356,47,r'$Z(x)\in\{0,1\}$',9.4,color=T)
    d.txt(348,24,'One trial per null input',8.7,color=G)
    return d

FIGURES={'mixture-transport':mixture_transport,'calibration-unit':calibration_unit}
