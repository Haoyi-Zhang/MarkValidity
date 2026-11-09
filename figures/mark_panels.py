"""Distinct views of the evaluation contract and the retained measurements."""
import numpy as np
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from matplotlib.patches import Rectangle
from matplotlib.ticker import PercentFormatter
from visual_grammar import *


def architecture(out):
    d=Diagram(h=173)
    d.text(9,160,'One task and declared protocol',10,BLUE,'left',True)
    d.text(303,160,'What the evidence supports',9.2,MUTED,'left',True)
    d.line((20,27),(20,144),c=GRID,lw=1.2)
    entries=[
        (132,'A','Semantics','Matched runs on the same inputs','Equality on the domain',BLUE,PALE),
        (97,'B','Source form','Paired source representations','Structural change',TEAL,GREEN),
        (62,'C','Attack response','Detection by attack and severity','Workload-specific survival',RED,WARM),
        (27,'D','Calibration','Null trials at one threshold','False-alarm bound',PURPLE,PALE),
    ]
    for y,letter,title,observation,claim,c,fill in entries:
        d.line((20,y),(34,y),c=c)
        d.token(45,y,letter,c,fill)
        d.text(64,y+5,title,9.7,c,'left',True)
        d.text(64,y-7,observation,8.7,MUTED,'left')
        # Small diagram encodings distinguish pairs, edit locations, a design
        # grid and a repeated trial from a single generic box shape.
        if letter in ('A','B'):
            for j in range(5):
                x=221+j*8
                d.rect(x,y+2,5.5,4.5,c if letter=='A' or j!=2 else fill,c,.55)
                d.rect(x,y-6.5,5.5,4.5,c if letter=='A' or j!=3 else fill,c,.55)
                if letter=='A':d.line((x+2.7,y-2),(x+2.7,y+2),c=c,lw=.55)
        elif letter=='C':
            for i in range(3):
                for j in range(5):d.dot(223+j*8,y-6+6*i,1.6,c,'white')
        else:
            for j in range(5):d.dot(223+j*8,y,2.1,c,'white')
        d.arrow((264,y),(294,y),c=c)
        d.text(303,y,claim,9.3,c,'left',True)
    d.finish(out)


def gate_geometry():
    fig=new(229,212)
    ax=plot_area(fig,(.22,.20,.73,.72),'both')
    ax.set(xlim=(.58,1.025),ylim=(.58,1.025),aspect='equal',
        xticks=[.6,.7,.8,.9,1],yticks=[.6,.7,.8,.9,1],
        xlabel='Executable-semantic score',ylabel='Calibration score')
    ax.tick_params(labelsize=9.6)
    ax.xaxis.label.set_size(10)
    ax.yaxis.label.set_size(10)
    ax.add_patch(Rectangle((.8,.8),.2,.2,fc=GREEN,ec=TEAL,lw=.8,zorder=1))
    for value,c,ls in ((1.64,BLUE,'--'),(1.70,RED,'-.')):
        xx=np.array([value-1,1])
        ax.plot(xx,value-xx,c=c,ls=ls,lw=.85)
    ax.scatter([.82],[.82],c=TEAL,marker='o',s=25,zorder=4)
    ax.scatter([1],[.70],c=RED,marker='D',s=22,zorder=4)
    ax.annotate('A',(.82,.82),xytext=(13,12),textcoords='offset points',color=INK,weight='bold',fontsize=10)
    ax.annotate('B',(1,.70),xytext=(-9,-19),textcoords='offset points',ha='right',
                color=RED,weight='bold',fontsize=10,bbox=dict(facecolor='white',edgecolor='none',pad=.55))
    ax.axhline(.8,color=TEAL,lw=.55,ls=':')
    ax.axvline(.8,color=TEAL,lw=.55,ls=':')
    return fig


def fingerprint(rows):
    values=np.empty((9,4))
    for x,y,v in rows:
        if x!=int(x) or y!=int(y) or not (1<=x<=4 and 1<=y<=9):raise ValueError((x,y))
        values[int(y)-1,int(x)-1]=v
    names=['Payload match','Carrier retention','Identifier style','Identifier multiset','Control profile',
           'AST type','ID/number-normalized','Token','Character']
    fig=new(425,221)
    ax=plot_area(fig,(.248,.115,.617,.8),None)
    cmap=LinearSegmentedColormap.from_list('signed',[BLUE,'#fcfcfb',RED])
    mesh=ax.pcolormesh(values,cmap=cmap,norm=TwoSlopeNorm(vmin=-1,vcenter=0,vmax=1),
                       edgecolors='white',lw=.8,rasterized=False)
    ax.set(xticks=np.arange(4)+.5,xticklabels=['Format','Identifier','Structure','Delete'],
           yticks=np.arange(9)+.5,yticklabels=names)
    ax.invert_yaxis();ax.xaxis.tick_top();ax.tick_params(length=0,labelsize=9.7)
    for spine in ax.spines.values():spine.set_visible(False)
    for x,y,v in rows:
        ax.text(x-.5,y-.5,f'{v:+.2f}' if abs(v)>=.005 else '0.00',ha='center',va='center',
                fontsize=9.8,color='white' if abs(v)>.66 else INK,
                weight='bold' if abs(v)>=.5 else 'normal')
    cax=fig.add_axes((.892,.20,.024,.60))
    cb=fig.colorbar(mesh,cax=cax,ticks=[-1,-.5,0,.5,1])
    cb.solids.set_rasterized(False)
    cb.ax.tick_params(length=0,labelsize=9.3,pad=3)
    cb.outline.set_linewidth(.4)
    fig.text(.248,.042,'Standardized intervention coefficient',fontsize=9.5,color=MUTED)
    return fig


SERIES=(('lexical','Lexical',BLUE,'-','o'),('structural','Structural',MUTED,'--','s'),
        ('hybrid','Hybrid',TEAL,'-.','^'))


def frontier(rows):
    fig=new(383,183)
    ax=plot_area(fig,(.124,.24,.83,.64),'y')
    ax.set(xlim=(0,1),ylim=(.20,.72),xticks=np.arange(5)/4,
        yticks=np.arange(.2,.71,.1),xlabel='Targeted mass assigned to renaming',ylabel='Mixture score')
    ax.tick_params(labelsize=9.6)
    ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    for name,label,color,ls,mark in SERIES:
        ax.plot(rows['rename_share'],rows[name],c=color,ls=ls,lw=1.36,marker=mark,markevery=20,
                ms=4.0,mfc='white',mew=.85,label=label)
    ax.axvline(.500919,color=MUTED,ls=':',lw=.85)
    ax.annotate('Tie at 50.0919%',(.500919,.46),xytext=(.52,.64),ha='left',
                fontsize=9.7,color=INK,arrowprops={'arrowstyle':'-','color':MUTED,'lw':.7},
                bbox={'facecolor':'white','edgecolor':'none','pad':1})
    ax.legend(loc='lower center',bbox_to_anchor=(.5,1),ncol=3,frameon=False,fontsize=9.6)
    return fig


def attack(output,reader):
    fig=new(428,238)
    for k,(key,title) in enumerate((('rename','Identifier renaming'),('normalize','Structural normalization'),
                                   ('strip','Carrier stripping'),('mixed','Mixed intervention'))):
        x=(.125,.572)[k%2];y=(.550,.158)[k//2]
        ax=plot_area(fig,(x,y,.384,.268),'y')
        ax.set(xlim=(-.012,1.012),ylim=(-.04,1.04),xticks=[0,.25,.5,.75,1],yticks=[0,.5,1])
        ax.set_xticklabels(['0','.25','.50','.75','1'])
        ax.tick_params(labelsize=9.6)
        ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
        if k%2:ax.tick_params(labelleft=False)
        if k<2:ax.tick_params(labelbottom=False)
        ax.set_title(f'({chr(97+k)}) {title}',loc='left',pad=8,fontweight='bold',fontsize=9.8)
        for j,(name,label,c,ls,m) in enumerate(SERIES):
            rows=reader(f'{key}-{name}.dat')
            xx=[float(r['severity']) for r in rows];yy=[float(r['rate']) for r in rows]
            ax.plot(xx,yy,c=c,ls=ls,lw=1.35,marker=m,ms=4.2,markevery=(j,3),
                mfc='white' if j else c,mew=.85,label=label,clip_on=False)
        if k==0:
            handles,labels=ax.get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',ncol=3,frameon=False,bbox_to_anchor=(.54,.998),
               handlelength=2.5,columnspacing=1.8,fontsize=9.5)
    fig.text(.52,.047,'Requested severity',ha='center')
    fig.text(.028,.52,'Detection rate',va='center',rotation=90)
    save(fig,output)


def protocol_transfer(out,reader):
    fig=new(425,249)
    a=plot_area(fig,(.291,.48,.669,.37),None)
    for x in (1,2,3):a.axvline(x,color=GRID,lw=.6,zorder=0)
    rules=['Native exact-tail','SrcMarker bit','SrcMarker message','CodeIP-inspired',
           'SWEET AUROC','SWEET TPR .01','SWEET TPR .05']
    a.set(yticks=list(range(1,8)),yticklabels=rules,ylim=(.45,7.55),xlim=(.58,3.65),
          xticks=[1,2,3],xticklabels=[s[1] for s in SERIES])
    a.xaxis.tick_top()
    a.tick_params(labelsize=10)
    fig.text(.021,.945,'(a) Winning carrier by scoring rule',weight='bold')
    for j,(name,_,c,_,m) in enumerate(SERIES):
        for row in reader(f'figdata/protocol-{name}.dat'):
            x,y,v=[float(row[k]) for k in ('x','y','value')]
            a.scatter(x,y,s=28,marker=m,c=c,zorder=4)
            a.annotate(f'{v:.3f}',(x,y),xytext=(8,0),textcoords='offset points',va='center',fontsize=10)
    b=plot_area(fig,(.291,.155,.669,.178),'x')
    b.set(yticks=[1,2,3],yticklabels=['Scope-blind collapse','Syntax-aware rename','Inert comment'],
          ylim=(.5,3.5),xlim=(-.02,1.17),xticks=np.arange(5)/4,xlabel='Parse-and-compile success')
    b.xaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    b.tick_params(labelsize=10)
    fig.text(.021,.381,'(b) Transfer to selected modules',weight='bold')
    for f,c,m in (('transfer-controls',TEAL,'o'),('transfer-negative',RED,'^')):
        for row in reader(f'figdata/{f}.dat'):
            rate,y,lo,hi=[float(row[k]) for k in ('rate','y','eminus','eplus')]
            b.errorbar(rate,y,xerr=[[lo],[hi]],fmt=m,color=c,ms=4,capsize=2,lw=1.05)
            b.annotate(row['label'],(rate+hi,y),xytext=(7,0),textcoords='offset points',va='center',fontsize=9.9)
    save(fig,out)
