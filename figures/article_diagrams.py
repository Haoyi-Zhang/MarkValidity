"""Separate measurement channels; admit evidence before using it."""
import csv
from pathlib import Path

from diagram_ink import Diagram,S,T,A,K,G,F,L,P,O


def full_rename_counts():
    path=Path(__file__).resolve().parents[1]/'results/derived/response_curves.csv'
    with path.open(encoding='utf8',newline='') as f:
        return {r['scheme']:(int(r['successes']),int(r['trials'])) for r in csv.DictReader(f)
                if r['attack']=='rename' and float(r['severity'])==1}


def architecture():
    d=Diagram(428,102)
    d.tag(10,91,'Three observation units')
    d.txt(24,48,r'$x$',10.1,color=S)
    for y,p in ((67,'P'),(32,'Q')):
        d.wire((34,48),(56,y),(70,y),c=S)
        d.mark('code',81,y,13,S)
        d.txt(101,y,'$'+p+'$',9.6,color=S)
        d.wire((111,y),(124,y),c=S)
        d.txt(142,y,'$o_'+p+'$',10,color=S)
    d.txt(93,11,'Paired execution',8.9)
    for y,seq in ((65,'abc'),(33,'bac')):
        for x,ch in zip((188,214,240),seq):
            c=S if ch=='a' else T if ch=='b' else G
            d.dotmark(x,y,5.9,c=c)
            d.node_label(x,y,ch,8.8,color=c)
    d.wire((188,57),(214,41),c=S,dash=True,arrow=False)
    d.wire((214,57),(188,41),c=T,dash=True,arrow=False)
    d.txt(215,11,'Token permutation',8.9)
    for y,label,c in ((67,r'$D(P)$',S),(32,r"$D(P')$",A)):
        d.mark('array' if y==67 else 'patch',309,y,15,c)
        d.wire((320,y),(349,y),c=c)
        d.txt(374,y,label,9.8,color=c)
    d.wire((309,57),(309,42),c=A,dash=True)
    d.txt(346,11,'Carrier edit',8.9)
    return d


def evidence_routes():
    d=Diagram(420,120)
    d.tag(12,108,'Detection')
    d.tag(141,108,'Behavior')
    d.tag(276,108,'Lower')
    d.tag(350,108,'Upper')
    d.mark('lens',34,65,17,S)
    d.wire((46,65),(68,65),c=S)
    d.diamond(75,65,5.3,S)
    d.wire((82,65),(119,65),c=T)
    d.txt(99,79,'Yes',8.8,color=T)
    d.wire((75,58),(75,14),(135,14),c=G,dash=True)
    d.txt(149,14,'No detection',8.9,ha='left',color=G)
    d.dotmark(126,65,1.8,c=T,fill=T)
    for y,label,c,bits in ((87,'Valid',T,(1,1)),(63,'Unresolved',A,(0,1)),(39,'Invalid',G,(0,0))):
        d.wire((130,65),(147,y),(157,y),c=c,arrow=False)
        d.txt(167,y,label,9.2,ha='left',color=c)
        for x,b in zip((291,366),bits):
            d.mark('check' if b else 'reject',x,y,12,c)
    for x in (291,366):d.mark('reject',x,14,12,G)
    return d


def claim_channels():
    d=Diagram(428,138)
    d.tag(10,128,'Inputs')
    d.tag(125,128,'Claim Calculus')
    d.tag(305,128,'Supported Claim')
    d.mark('code',17,85,15,S)
    d.txt(30,97,r'$y\ \%\ 400=0$',9.5,ha='left',color=S)
    d.txt(30,73,r'$y\ \%\ 800=0$',9.5,ha='left',color=A)
    d.wire((83,97),(98,97),(106,85),c=S,arrow=False)
    d.wire((83,73),(98,73),(106,85),c=A,arrow=False)
    d.dotmark(106,85,1.6,c=K,fill=K)
    d.wire((108,86),(122,102),c=A)
    d.wire((108,84),(122,77),c=S)
    counts=full_rename_counts()
    sh,sn=counts['structural']
    lh,ln=counts['lexical']
    d.mark('code',18,43,15,T)
    d.txt(29,43,'Marked code',9.5,ha='left',color=T)
    d.wire((87,43),(122,43),c=T)
    d.mark('array',18,15,15,G)
    d.txt(29,15,'24 fair bits',9.5,ha='left',color=G)
    d.wire((87,15),(122,15),c=G)
    for y,title,evidence,finding,c in (
        (102,'Execute',r'$1200:\ \mathrm{T}\ne\mathrm{F}$','Refutes equivalence',A),
        (77,'Normalize',r'$\mathrm{ID}\,\%\,\mathrm{N}=\mathrm{N}$','Token match only',S),
        (43,'Full rename',f'S {sh}/{sn}; L {lh}/{ln}','Modeled survival',T),
        (15,'Test the null',r'$\geq22$ matches',r'$P(\mathrm{accept}\mid H_0)=1.7941\times10^{-5}$',G),
    ):
        d.txt(126,y,title,9.6,ha='left',color=c,bold=True)
        d.txt(232,y,evidence,9.2,color=c)
        d.wire((276,y),(299,y),c=c)
        d.txt(305,y,finding,9.4,ha='left',color=c)
    # A local boundary, not a fourth evidence flow: normalized tokens
    # cannot be substituted for the execution premise.
    d.wire((391,82),(391,92),c=G,dash=True,arrow=False)
    d.wire((387,92),(395,92),c=G,arrow=False)
    d.txt(383,88,'No semantic inference',7.5,ha='right',color=G)
    d.txt(231,30,'S: structural; L: lexical',8.0,color=G)
    return d


def source_erasure():
    d=Diagram(420,111)
    d.mark('code',26,54,21,S)
    d.txt(31,30,'Compiled',9.0)
    d.wire((41,54),(69,54),c=S,arrow=False)
    d.dotmark(69,54,1.8,c=S,fill=S)
    for y,k,lab,check,c in ((82,'code','Erased prefix','Rule holds?',A),
                            (29,'graph','Remaining AST','Matches reference?',S)):
        d.wire((73,54),(100,y),c=c)
        d.mark(k,111,y,16,c)
        d.txt(122,y,lab,9.0,ha='left',color=c)
        d.txt(238,y,check,9.0)
        d.wire((286,y),(295,y),(303,54),c=c,arrow=False)
    d.mark('code',209,53,12,G)
    d.txt(221,53,'Reference task',8.7,ha='left',color=G)
    d.wire((209,47),(209,37),c=G,dash=True)
    d.dotmark(312,54,6,c=T)
    d.node_label(312,54,r'$\wedge$',9.5,color=T)
    d.wire((320,56),(342,73),c=T)
    d.mark('check',354,74,11,T)
    d.txt(365,74,'Admit',9.1,ha='left',color=T)
    d.wire((320,51),(343,34),c=A,dash=True)
    d.mark('reject',354,33,11,A)
    d.txt(365,33,'Reject',9.1,ha='left',color=A)
    return d


FIGURES={f.__name__.replace('_','-'):f for f in (
    architecture,evidence_routes,claim_channels,source_erasure)}
