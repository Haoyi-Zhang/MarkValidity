"""Separate measurement channels; admit evidence before using it."""
from diagram_ink import Diagram,S,T,A,K,G,F,L,P,O


def architecture():
    d=Diagram(428,102)
    d.tag(6,91,'(a) Paired execution')
    d.tag(143,91,'(b) Token permutation')
    d.tag(280,91,'(c) Carrier intervention')
    d.txt(15,43,r'$x$',11,color=S)
    d.wire((23,43),(34,43),(34,64),(54,64),c=S)
    d.wire((34,43),(34,22),(54,22),c=S)
    d.dotmark(34,43,2,c=S,fill=S)
    for y,letter in [(64,'P'),(22,'Q')]:
        d.mark('code',64,y,15,S)
        d.txt(76,y,fr'$\mathit{{{letter}}}$',10,ha='left',color=S)
        d.wire((89,y),(101,y),c=S)
        d.txt(115,y,fr'$o_{letter}$',10.3,color=S)
    for y,tokens in [(64,'abc'),(22,'bac')]:
        for k,ch in enumerate(tokens):
            x=153+25*k
            d.block(x,y-7,17,14,T,'white')
            d.node_label(x+8.5,y,ch,9.1,color=T)
    d.wire((187,53),(187,33),c=T)
    d.txt(201,43,'Reorder',9.0,ha='left',color=T)
    for y,artifact,result,c in [(64,'array',r'$D(P)$',S),(22,'array',r"$D(P')$",A)]:
        d.mark(artifact,301,y,22,c)
        d.wire((315,y),(344,y),c=c)
        d.mark('lens',355,y,16,c)
        d.txt(371,y,result,10.0,ha='left',color=c)
    d.wire((301,51),(301,35),c=A,dash=True)
    d.txt(315,43,'Edit',9.0,ha='left',color=A)
    return d


def evidence_routes():
    d=Diagram(420,120)
    d.mark('lens',30,59,23)
    d.txt(30,40,'Detector',9.3)
    d.wire((46,59),(85,59),c=S)
    d.diamond(93,59,6,S)
    d.wire((93,67),(93,101),(321,101),c=G)
    d.txt(151,110,'No detection',9.4,color=G)
    d.wire((101,59),(187,59),c=T)
    d.txt(137,70,'Detected',9.4,color=T)
    d.mark('cert',200,59,20,T)
    d.txt(199,39,'Validity',9.3)
    d.wire((215,59),(235,59),c=G,arrow=False)
    d.dotmark(235,59,1.9,c=G,fill=G)
    for y,lab,c,status in [(76,'Valid',T,(True,True)),(49,'Unresolved',A,(False,True)),(23,'Invalid',G,(False,False))]:
        d.wire((235,59),(249,y),(316,y),c=c,dash=c!=T)
        d.txt(285,y+9,lab,9.1,color=c)
        for x,b in zip((344,389),status):
            d.mark('check' if b else 'reject',x,y,13,c)
    for x,lab in [(344,'Lower'),(389,'Upper')]:
        d.txt(x,112,lab,9.3,bold=True)
        d.mark('reject',x,101,13,G)
    return d


def claim_channels():
    d=Diagram(420,69)
    for x,k,t,c in [(22,'code','Program pair',S),(226,'lens','Detector trials',T)]:
        d.mark(k,x,34,23,c)
        d.txt(x+6,12,t,9.0,color=c)
        d.wire((x+16,34),(x+46,34),c=c,arrow=False)
        d.dotmark(x+46,34,1.6,c=c,fill=c)
    for x,k,y,t,c in [(94,'trace',52,'Observed behavior',S),
                      (94,'graph',15,'Source structure',S),
                      (299,'patch',52,'Survival under edits',T),
                      (299,'array',15,'Null calibration',T)]:
        d.wire((x-26,34),(x-17,y),(x-10,y),c=c)
        d.mark(k,x,y,14,c)
        d.txt(x+14,y,t,9.3,ha='left',color=c)
    return d


def source_erasure():
    d=Diagram(420,55)
    d.mark('code',25,33,17,S)
    d.txt(25,46,'Candidate',8.6)
    for x,label in [(81,'Parse / compile'),(222,'Match reference'),(300,'Check prefix')]:
        d.diamond(x,33,5,S)
        d.txt(x,46,label,8.9)
        d.wire((x,26),(x,9),c=A,dash=True,arrow=False)
    d.mark('graph',151,33,19,S)
    d.txt(151,46,'Erase prefix',8.9)
    for left,right in [(36,73),(89,138),(164,214),(230,292)]:
        d.wire((left,33),(right,33),c=S)
    d.wire((308,33),(355,33),c=T)
    d.mark('check',366,33,17,T)
    d.txt(379,33,'Admit',8.8,ha='left',color=T)
    for x in (222,300):
        d.dotmark(x,9,1.5,c=A,fill=A)
    d.wire((81,9),(355,9),c=A,dash=True)
    d.mark('reject',366,9,17,A)
    d.txt(379,9,'Reject',8.8,ha='left',color=A)
    return d


FIGURES={f.__name__.replace('_','-'):f for f in (
    architecture,evidence_routes,claim_channels,source_erasure)}
