"""Evaluation architecture and retained-data panels for MarkValidity."""
import csv
import json
from math import comb
from pathlib import Path
from pictograms import icon

from figure_style import (AMBER, BLUE, INK, LIGHT, MINT, MUTED, RULE, SAND, SERIES, TEAL,
                          Plate, arguments, grid, paper_style, plot, plt, save)

HERE=Path(__file__).resolve().parent
DATA=HERE/'data'

def retained(name):
    with (DATA/(name+'.dat')).open(encoding='utf-8-sig') as f:
        rows=[x.split() for x in f if x.strip()]
    return [dict(zip(rows[0],x,strict=True)) for x in rows[1:]]

def architecture(out,preview):
    from diagram_ink import emit
    emit('architecture',out,preview)

def calibration(out,preview):
    from matplotlib.lines import Line2D
    # Exact probability mass, independent of any generated illustration.
    prob=[comb(24,k)/2**24 for k in range(25)]
    assert abs(sum(prob)-1)<1e-12
    assert sum(prob[22:])==301/2**24
    f,a=plot(426,119,left=54,right=16,bottom=31,top=22)
    floor=3e-8
    a.vlines(range(22),floor,prob[:22],color=BLUE,lw=1.4)
    a.vlines(range(22,25),floor,prob[22:],color=AMBER,lw=1.45)
    a.scatter(range(22,25),prob[22:],marker='D',s=14,color=AMBER,zorder=4)
    a.axvline(21.5,color=MUTED,lw=.65,ls='--')
    a.set(yscale='log',xlim=(-.6,24.6),ylim=(floor,.4),
          xticks=[0,6,12,18,22,23,24],yticks=[1e-7,1e-5,1e-3,1e-1],
          xlabel='Matching bits',ylabel='Probability mass')
    a.minorticks_off()
    a.tick_params(labelsize=9)
    a.legend(handles=[
        Line2D([],[],color=BLUE,marker='|',markersize=8,markeredgewidth=1.4,
               linestyle='none',label='Below threshold (0 to 21)'),
        Line2D([],[],color=AMBER,marker='D',markersize=4,
               linestyle='none',label='Acceptance tail (22 to 24)'),
    ],ncol=2,loc='lower left',bbox_to_anchor=(0,1.02),fontsize=9,handlelength=1.15)
    grid(a);save(f,out,'fair-bit-calibration',preview)

def responses(out,preview):
    f, axs=plt.subplots(2,2,figsize=(426/72,233/72),sharex=True,sharey=True)
    f.subplots_adjust(left=.114,right=.965,bottom=.162,top=.78,wspace=.24,hspace=.61)
    rowspec=[('rename','(a) Identifier renaming'),('normalize','(b) Structural normalization'),
             ('strip','(c) Carrier stripping'),('mixed','(d) Mixed intervention')]
    for a,(kind,title) in zip(axs.flat,rowspec):
        for j,(carrier,(col,mark,ls)) in enumerate(zip(['lexical','structural','hybrid'],SERIES)):
            rows=retained(kind+'-'+carrier)
            x=[float(r['severity']) for r in rows];y=[float(r['rate']) for r in rows]
            assert x==[k/10 for k in range(11)]
            lo=[float(r['lower']) for r in rows];hi=[float(r['upper']) for r in rows]
            assert all(0<=l<=v<=h<=1 for l,v,h in zip(lo,y,hi))
            assert all(abs(v*384-round(v*384))<1e-8 for v in y)
            a.plot(x,y,color=col,marker=mark,ls=ls,markevery=list(range(j,11,3)),
                   markersize=3.8,mew=.66,mfc='white',lw=.85,label=carrier.title())
        a.set(xlim=(-.025,1.025),ylim=(-.08,1.08),xticks=(0,.5,1),yticks=(0,.5,1))
        a.set_xticklabels(('0','0.5','1'))
        a.set_yticklabels(('0','0.5','1'))
        a.tick_params(length=2.4,width=.55,labelsize=9)
        a.set_title(title,loc='left',pad=4.5,fontsize=10)
        grid(a,'y')
    handles,labels=axs[0,0].get_legend_handles_labels()
    f.legend(handles,labels,loc='upper center',bbox_to_anchor=(.54,.991),ncol=3,
             fontsize=9.6,handlelength=2.2)
    f.text(.032,.47,'Detection rate',rotation=90,va='center',ha='center',fontsize=9.8)
    f.text(.54,.029,'Requested severity',ha='center',fontsize=9.8)
    save(f,out,'attack-response',preview)

def transfer(out,preview):
    d=Plate(399.7,201)
    d.head(9,188,'(a) Winning carrier by rule')
    names=['Lexical','Structural','Hybrid']
    rules=['Native exact-tail','SrcMarker bit','SrcMarker message','CodeIP-inspired',
           'SWEET AUROC','SWEET TPR (1% FPR)','SWEET TPR (5% FPR)']
    xs=(121,170,215)
    observed={}
    for carrier in (s.lower() for s in names):
        for r in retained('protocol-'+carrier):
            x,y,v=[float(r[k]) for k in ('x','y','value')]
            assert names[int(x)-1].lower()==carrier and y not in observed
            observed[int(y)]=(int(x)-1,v)
    assert set(observed)==set(range(1,8))
    for x,name in zip(xs,names):d.text(x,165,name,8.6,weight='bold')
    for i,label in enumerate(rules):
        y=147-18*i
        d.text(9,y,label,8.9,ha='left')
        winner,score=observed[7-i]
        for j,x in enumerate(xs):
            tone,_,_=SERIES[j]
            if j==winner:
                d.dot(x-15,y,'',fill=tone,edge=tone,r=2)
                d.text(x+1,y,f'{score:.3f}',9.1,color=tone,weight='bold')
    d.head(248,188,'(b) Edits that parse and compile')
    labels={1:'Scope-blind collapse',2:'Syntax-aware rename',3:'Inert comment'}
    for name,col in [('transfer-controls',TEAL),('transfer-negative',AMBER)]:
        for r in retained(name):
            x,n=map(int,r['label'].split('/'))
            y=int(r['y'])
            assert n==120 and abs(x/n-float(r['rate']))<1e-10
            yy=30+39*y
            d.text(248,yy+11,labels[y],9.1,ha='left')
            d.frame(248,yy-3.5,102,7,'#edf0f2','#edf0f2')
            d.frame(248,yy-3.5,102*x/n,7,col,col)
            d.text(357,yy,r['label'],9.1,ha='left',color=col,weight='bold')
    d.text(248,42,'Share of 120 modules',8.7,ha='left',color=MUTED)
    d.save(out,'protocol-transfer',preview)

def coverage(out,preview):
    # Exact groups from the current nominal/complete mutation experiment.
    # Use the retained effective-mutant records rather than a mock dataset.
    with (HERE/'../results/raw/mutants.csv').open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    assert len(rows)==72
    truth=lambda r,k:r[k].lower() in {'true','1','yes'}
    counts=[sum(truth(r,'nominal_equal') for r in rows),sum(truth(r,'full_domain_equal') for r in rows)]
    assert counts==[6,0],counts
    examples=[('leap_year','Leap-year exception','1200','true','false',0),
              ('darts','Dart-score radius','(−10, 0)','1 point','0 points',62),
              ('nucleotide_count','Nucleotide channels','C','C: 1','G: 1',2)]
    survivors=[r for r in rows if truth(r,'nominal_equal')]
    assert {r['task'] for r in survivors}=={x[0] for x in examples}
    d=Plate(426,183)
    order=[key for key,*_ in examples]+sorted({r['task'] for r in rows}-{x[0] for x in examples})
    langs=('python','javascript')
    tests={(r['task'],r['language'],int(r['mutant_id'])):r for r in rows}
    assert len(tests)==72 and set(tests)=={(key,l,m) for key in order for l in langs for m in (1,2,3)}
    distinguished='#718698'
    for i,(title,field,miss) in enumerate([('Nominal tests','nominal_equal',6),
                                           ('Complete execution','full_domain_equal',0)]):
        x=11+i*215
        d.head(x,170,f'({chr(97+i)}) {title}')
        for j,key in enumerate(order):
            for a,lang in enumerate(langs):
                for m in (1,2,3):
                    missed=truth(tests[key,lang,m],field)
                    xx=x+26+8*j
                    yy=145-7*(m-1)-26*a
                    if missed:
                        d.ax.plot(xx,yy,'x',ms=3.8,mew=.9,color=AMBER)
                    else:
                        d.dot(xx,yy,'',fill=distinguished,edge=distinguished,r=1.5)
        for j in range(len(examples)):
            d.text(x+26+8*j,156,str(j+1),8.3,color=MUTED)
        d.text(x,138,'Py',9.2,ha='left',color=MUTED)
        d.text(x,112,'JS',9.2,ha='left',color=MUTED)
        d.text(x+125,141,f'{miss} / 72',12.5,ha='left',weight='bold',color=AMBER if miss else TEAL)
        d.text(x+125,123,'mutants missed',9,ha='left',color=MUTED)
    d.ax.plot(13,89,'x',ms=3.8,mew=.9,color=AMBER)
    d.text(20,89,'Missed',8.7,ha='left',color=AMBER)
    d.dot(63,89,'',fill=distinguished,edge=distinguished,r=1.5)
    d.text(70,89,'Distinguished',8.7,ha='left',color=MUTED)
    d.head(11,66,r'(c) First distinguishing inputs and outputs (reference $\rightarrow$ mutant)')
    for i,(key,title,inp,ref,mut,index) in enumerate(examples):
        rr=[r for r in survivors if r['task']==key]
        assert {r['language'] for r in rr}==set(langs)
        assert all(int(r['first_mismatch_index'])==index and not truth(r,'full_domain_equal') for r in rr)
        x=11+i*139
        d.text(x,49,f'{i+1}  {title}',9.3,ha='left',weight='bold')
        d.text(x,37,f'Input: {inp}',9,ha='left',color=MUTED)
        d.text(x,23,fr'{ref} $\rightarrow$ {mut}',9.4,ha='left')
    d.save(out,'nominal-survivors',preview)

def joint_bounds(out,preview):
    s=json.loads((HERE/'../results/evidence-policies/summary.json').read_text(encoding='utf8'))
    keys=['execution_only','proof_supported']
    obs=[s[k] for k in keys]
    assert not s['historical_labels_changed'] and s['task_programs_executed']==0
    assert [r['denominator'] for r in obs]==[76032,76032]
    assert [(r['lower_numerator'],r['upper_numerator']) for r in obs]==[(122,75722),(17955,55755)]
    f=plt.figure(figsize=(420/72,162/72))
    a=f.add_axes([.253,.202,.715,.648])
    pct=lambda n,r:100*n/r['denominator']
    for y,r in zip((1.08,.18),obs):
        nums=[r['detected'],r['unknown'],r['known']-r['detected']]
        assert sum(nums)==r['denominator'] and nums[0]+nums[1]==r['upper_numerator']
        left=0.
        styles=((TEAL,'none',''),('#e4e9ee','#54697a','..'),(BLUE,'white','//'))
        for n,(c,edge,h) in zip(nums,styles,strict=True):
            v=pct(n,r)
            a.barh(y+.18,v,left=left,height=.20,color=c,edgecolor=edge,linewidth=.4,hatch=h)
            left+=v
        lo,hi=pct(r['lower_numerator'],r),pct(r['upper_numerator'],r)
        a.vlines([lo,hi],y-.09,y+.08,color=MUTED,lw=.55,ls=':')
        a.hlines(y-.09,lo,hi,color=INK,lw=1.2)
        a.plot([lo,hi],[y-.09,y-.09],linestyle='none',marker='|',color=INK,ms=6,clip_on=False)
        # Separate the evidence-supported lower endpoint from the upper endpoint
        # even when the filled green segment is sub-point at publication width.
        a.plot(lo,y-.09,marker='o',color=TEAL,mfc='white',mew=.85,ms=3.8,zorder=4,clip_on=False)
        a.text((lo+hi)/2,y-.27,f'{lo:.2f}% to {hi:.2f}%',fontsize=8.8,ha='center',va='center')
    a.set(xlim=(0,100),ylim=(-.23,1.52),yticks=(1.26,.36),
          yticklabels=('Execution only','Proof + execution'),xticks=(0,25,50,75,100))
    a.tick_params(axis='y',labelsize=8.8,length=0)
    from matplotlib.patches import Patch
    f.legend(handles=[Patch(facecolor=TEAL,label='Success known'),
                      Patch(facecolor='#e4e9ee',edgecolor='#54697a',hatch='..',label='Undetermined'),
                      Patch(facecolor=BLUE,edgecolor='white',hatch='//',label='Ruled out')],
             ncol=3,loc='upper center',bbox_to_anchor=(.58,.995),fontsize=8.3)
    a.set_xlabel('Share of the same 76,032 configurations (%)',labelpad=2)
    grid(a,'x');save(f,out,'joint-bounds',preview)

def evidence_routes(out,preview):
    from diagram_ink import emit
    emit('evidence-routes',out,preview)


if __name__=='__main__':
    args=arguments();paper_style()
    for draw in (architecture,calibration,responses,transfer,coverage,joint_bounds,evidence_routes):draw(args.outdir,args.previews)
    from diagram_ink import emit_supplemental
    emit_supplemental(args.outdir,args.previews)
