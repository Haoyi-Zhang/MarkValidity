"""Separate measurement channels; admit evidence before using it."""
from diagram_ink import Diagram,S,T,A,K,G,F,L,P,O


def architecture():
    d=Diagram(428,102)
    d.tag(6,91,'(a) Paired execution')
    d.tag(144,91,'(b) Token permutation')
    d.tag(283,91,'(c) Carrier intervention')
    d.txt(15,43,r'$x$',11,color=S)
    d.wire((24,43),(38,43),(38,65),(57,65),c=S)
    d.wire((38,43),(38,21),(57,21),c=S)
    d.dotmark(38,43,1.9,c=S,fill=S)
    for y,program,outcome in [(65,'P','o_P'),(21,'Q','o_Q')]:
        d.txt(67,y,fr'${program}$',10.4)
        d.wire((77,y),(100,y),c=S)
        d.txt(114,y,fr'${outcome}$',10.3,color=S)
    for y,tokens in [(65,'abc'),(21,'bac')]:
        for k,ch in enumerate(tokens):
            x=157+25*k
            d.block(x,y-7,18,14,T,'white')
            d.txt(x+9,y,ch,8.7,color=T)
    d.wire((191,54),(191,32),c=T)
    d.txt(207,43,'Permute',8.7,ha='left',color=T)
    d.mark('array',312,65,25,S);d.mark('array',312,21,25,A)
    d.wire((312,53),(312,34),c=A,dash=True)
    d.txt(301,43,'Edit',8.7,ha='right',color=A)
    d.wire((326,65),(362,65),c=S)
    d.wire((326,21),(362,21),c=A)
    d.mark('lens',374,65,15,S);d.mark('lens',374,21,15,A)
    d.txt(393,65,r'$D(P)$',9.3,ha='left',color=S)
    d.txt(393,21,r"$D(P')$",9.3,ha='left',color=A)
    return d


def evidence_routes():
    d=Diagram(420,120)
    d.mark('lens',31,59,23)
    d.txt(31,36,'Detector',9.1)
    d.wire((45,59),(84,59),c=S)
    d.diamond(92,59,6,S)
    d.wire((92,66),(92,99),(287,99),c=S)
    d.txt(146,109,'No detection',9.1,color=S)
    d.txt(302,99,'Neither bound',9.2,ha='left',color=S)
    d.wire((99,59),(190,59),c=T)
    d.txt(136,69,'Detection',9.1,color=T)
    d.mark('cert',201,59,21,T);d.txt(201,40,'Validity',8.6)
    d.wire((213,59),(241,59),(241,74),(287,74),c=T)
    d.wire((241,59),(241,49),(287,49),c=A,dash=True)
    d.wire((241,49),(241,24),(287,24),c=S)
    for y,lab,result,c in [(74,'Valid','Both bounds',T),(49,'Unresolved','Upper only',A),
                           (24,'Invalid','Neither bound',S)]:
        d.txt(263,y+9,lab,8.3,color=c)
        d.txt(302,y,result,9.2,ha='left',color=c)
    return d


def claim_channels():
    d=Diagram(420,69)
    d.mark('code',20,35,22,S)
    d.txt(37,35,'Program pair',9.2,ha='left',color=S)
    d.wire((94,35),(112,35),(112,53),(136,53),c=S)
    d.wire((112,35),(112,16),(136,16),c=S)
    d.txt(142,53,'Behavior',9.1,ha='left')
    d.txt(142,16,'Structure',9.1,ha='left')
    d.mark('lens',229,35,22,T)
    d.txt(246,35,'Detector trials',9.2,ha='left',color=T)
    d.wire((310,35),(327,35),(327,53),(346,53),c=T)
    d.wire((327,35),(327,16),(346,16),c=T)
    d.txt(352,53,'Attack survival',8.9,ha='left')
    d.txt(352,16,'Null calibration',8.9,ha='left')
    return d


def source_erasure():
    d=Diagram(420,55)
    d.mark('code',25,34,20);d.txt(25,13,'Candidate',8.5)
    d.wire((39,34),(76,34),c=S)
    d.diamond(83,34,5,S);d.txt(83,46,'Parse / compile',8.45)
    d.wire((89,34),(157,34),c=S)
    d.diamond(164,34,5,S);d.txt(164,46,'Check prefix',8.45)
    d.wire((170,34),(243,34),c=T)
    d.mark('graph',252,34,17,T);d.txt(252,46,'Erased AST',8.45,color=T)
    d.wire((263,34),(314,34),c=T)
    d.diamond(321,34,5,T);d.txt(321,46,'Match?',8.45)
    d.wire((321,12),(321,28),c=G)
    d.txt(310,10,'Reference AST',8.5,ha='right')
    d.wire((328,34),(360,34),c=T)
    d.mark('check',370,34,17,T);d.txt(384,34,'Admit',8.7,ha='left')
    return d


FIGURES={f.__name__.replace('_','-'):f for f in (
    architecture,evidence_routes,claim_channels,source_erasure)}
