#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

ART=Path(__file__).resolve().parent
ROOT=ART.parent
PAPER=ROOT/'paper'
RESULTS=ART/'results'

class VerificationError(RuntimeError):pass

def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def run(cmd,cwd=None,env=None):
 e=os.environ.copy();e.update({'PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'C.UTF-8','TZ':'UTC'})
 if env:e.update(env)
 p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,env=e)
 if p.returncode:raise VerificationError(f"command failed: {' '.join(cmd)}\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}")
 return p.stdout+p.stderr
def pdfinfo(path):
 out=run(['pdfinfo',str(path)])
 def val(k):
  m=re.search(r'^'+re.escape(k)+r':\s*(.+)$',out,re.M);return m.group(1).strip() if m else None
 return {'pages':int(val('Pages')),'page_size':val('Page size'),'encrypted':val('Encrypted')}
def result_hashes():
 return {p.relative_to(RESULTS).as_posix():sha(p) for p in RESULTS.rglob('*') if p.is_file()}
def fail(cond,msg):
 if not cond:raise VerificationError(msg)

# Root and debris.
fail({p.name for p in ROOT.iterdir()}=={"README.md", "artifact", "paper"},'project root must contain exactly three entries')
for p in ROOT.rglob('*'):
 fail(not p.is_symlink(),f'symlink forbidden: {p.relative_to(ROOT)}')
 if p.is_file():fail(p.stat().st_nlink==1,f'hardlink forbidden: {p.relative_to(ROOT)}')
 fail(p.name!='__pycache__' and p.suffix not in {'.pyc','.pyo'},f'cache forbidden: {p.relative_to(ROOT)}')
 fail(p.suffix.lower() not in {'.zip','.tar','.gz','.tgz','.7z','.rar'},f'nested archive forbidden: {p.relative_to(ROOT)}')

required=['main.tex','main.pdf','online-supplement.tex','online-supplement.pdf','references.bib','acmart.cls','ACM-Reference-Format.bst','build.sh','page_fit_audit.json','visual_qa.json','online_supplement_audit.json','citation_shape_audit.json','template_compliance_audit.json']
for name in required:fail((PAPER/name).is_file(),f'missing paper file: {name}')
fail({p.name for p in PAPER.glob('*.pdf')}=={'main.pdf','online-supplement.pdf'},'alternate manuscript PDF present')
fail(not (PAPER/'build-review.sh').exists(),'alternate manuscript build script present')

# Parse structured files.
for p in ROOT.rglob('*.json'):
 try:json.loads(p.read_text())
 except Exception as exc:raise VerificationError(f'invalid JSON {p.relative_to(ROOT)}: {exc}')
for p in ROOT.rglob('*.csv'):
 try:
  with p.open(newline='',encoding='utf-8') as f:list(csv.reader(f))
 except Exception as exc:raise VerificationError(f'invalid CSV {p.relative_to(ROOT)}: {exc}')

page=json.loads((PAPER/'page_fit_audit.json').read_text()); template=json.loads((PAPER/'template_compliance_audit.json').read_text()); contract=json.loads((ART/'contract_repair_audit.json').read_text())
fail(page['verdict']=='PASS','page audit not PASS')
fail(contract['verdict'].startswith('PASS'),'contract repair audit not PASS')

# PDF identity, size, integrity, and fonts.
for name,expected_pages,expected_sha in [('main.pdf',page['main_pages'],page['main_pdf_sha256']),('online-supplement.pdf',page['supplement_pages'],page['supplement_pdf_sha256'])]:
 p=PAPER/name; info=pdfinfo(p)
 fail(info['pages']==expected_pages,f'{name} page count mismatch')
 fail('612 x 792 pts' in info['page_size'],f'{name} not US Letter')
 fail(info['encrypted']=='no',f'{name} encrypted')
 fail(sha(p)==expected_sha,f'{name} hash mismatch')
 if shutil.which('qpdf'):run(['qpdf','--check',str(p)])
 fonts=run(['pdffonts',str(p)]).splitlines()[2:]
 fail(bool(fonts),f'no fonts in {name}')
 for line in fonts:
  if not line.strip():continue
  cols=line.split();fail(len(cols)>=6 and cols[4].lower()=='yes',f'unembedded font in {name}: {line}')

# Template source rules.
main=(PAPER/'main.tex').read_text();supp=(PAPER/'online-supplement.tex').read_text();joined=main+'\n'+supp
fail(r'\documentclass[manuscript,screen,review]{acmart}' in main,'wrong main documentclass')
fail(r'\documentclass[manuscript,screen,review]{acmart}' in supp,'wrong supplement documentclass')
for pat,msg in [(r'\\usepackage\{geometry\}|\\geometry\{','geometry override'),(r'\\(?:textwidth|textheight|oddsidemargin|evensidemargin|topmargin)\s*=','manual margin/text block'),(r'\\(?:linespread|setstretch|baselinestretch)','line spacing override'),(r'\\vspace\*?\{\s*-','negative vspace'),(r'\\acm(?:DOI|Volume|Number|Article|ISBN)\{[^}]+\}','unassigned production metadata')]:
 fail(not re.search(pat,joined,re.I),msg)

# Author technical consistency; no eligibility inference.
def meta(text):return {'authors':re.findall(r'\\author\{([^}]*)\}',text),'emails':re.findall(r'\\email\{([^}]*)\}',text),'orcids':re.findall(r'\\orcid\{([^}]*)\}',text),'institutions':re.findall(r'\\institution\{([^}]*)\}',text),'corresponding':text.count(r'\correspondingauthor')}
ma,ms=meta(main),meta(supp);fail(ma==ms,'main/supp author metadata differ');fail(len(ma['authors'])==len(ma['emails'])==len(ma['orcids']),'incomplete author metadata');fail(ma['corresponding']==1,'corresponding-author count mismatch')
for pdfname in ['main.pdf','online-supplement.pdf']:
 txt=run(['pdftotext','-f','1','-l','2','-layout',str(PAPER/pdfname),'-'])
 for a in ma['authors']:fail(a in txt,f'{pdfname} missing author {a}')
fail((ART/'AUTHOR_METADATA_CONFIRMATION_REQUIRED.md').exists(),'missing human author confirmation gate')

# Review line numbers.
try:
 import fitz
 doc=fitz.open(PAPER/'main.pdf');seq=[]
 for pg in doc:
  nums=[]
  for b in pg.get_text('dict')['blocks']:
   for line in b.get('lines',[]):
    for sp in line.get('spans',[]):
     t=sp['text'].strip();x0,y0,x1,y1=sp['bbox']
     if re.fullmatch(r'\d+',t) and x0<55 and float(sp['size'])<=8.5:nums.append((y0,int(t)))
  seq.extend(v for _,v in sorted(nums))
 fail(seq and seq==list(range(seq[0],seq[-1]+1)),'review line numbers missing or discontinuous')
 fail(seq[0]==page['line_numbers']['first'] and seq[-1]==page['line_numbers']['last'],'review line-number audit mismatch')
except ImportError:
 pass

# Citation and bibliography shape.
bib=(PAPER/'references.bib').read_text();bibkeys=re.findall(r'^@\w+\s*\{\s*([^,]+),',bib,re.M);cmds=[]
for m in re.finditer(r'\\cite(?:\[[^]]*\])?\{([^}]+)\}',main):cmds.append([x.strip() for x in m.group(1).split(',') if x.strip()])
keys=[x for group in cmds for x in group]
fail(all(len(x)==1 for x in cmds),'multi-key citation command')
fail(len(bibkeys)==82 and len(keys)==88 and len(set(keys))==82,'bibliography/citation count mismatch')
fail(set(keys)==set(bibkeys),'undefined or unused bibliography key')
with (ART/'citation_support.csv').open(newline='') as f:support=list(csv.DictReader(f))
fail(len(support)==88,'citation support row count mismatch')
fail(len(list((ART/'citation-evidence').glob('*.json')))==82,'citation evidence object count mismatch')
claim=json.loads((ART/'citation_claim_audit.json').read_text());fail(claim['verdict']=='PASS' and claim['positions']==88,'citation claim audit failed')
ref=json.loads((ART/'reference_metadata_audit.json').read_text());fail(ref['verdict']=='PASS' and ref['bibliography_entries']==82,'reference audit failed')

# Specific contract repairs in sources/results.
allpaper=main+'\n'+supp
for textval in ['33,016','GATT','GACT','letter','79927']:
 fail(textval in allpaper or textval in '\n'.join(p.read_text(errors='ignore') for p in (ART/'tests').glob('test*.py')),f'missing finite-domain witness {textval}')
fail(re.search(r'CodeIP.*(?:not applicable|inapplicable)',allpaper,re.I|re.S) is not None,'CodeIP applicability boundary missing')
fail(re.search(r'erasure-aware',allpaper,re.I) is not None,'local erasure-aware rule not named')
fail(re.search(r'same nominal|nominal.*does not',allpaper,re.I) is not None,'nominal severity caveat missing')
fail(re.search(r'hypothetical.*binomial|binomial.*reference',allpaper,re.I) is not None,'project interval scope missing')
fail(re.search(r'upper envelope|never leads',allpaper,re.I) is not None and not re.search(r'hybrid[^\n]{0,100}below both',allpaper,re.I),'mixture caption wording wrong')
for term in ['landmark','family means','duplication witness']:
 fail(term in supp.lower(),f'supplement missing {term}')

# Stale release assertions.
scan=[]
for p in ROOT.rglob('*'):
 if not p.is_file() or p.suffix.lower() not in {'.md','.json','.csv','.py','.tex','.txt','.sh'}:continue
 rel=p.relative_to(ROOT).as_posix()
 if any(x in rel for x in ['artifact/results/','artifact/corpus/','artifact/citation-evidence/']):continue
 scan.append(p.read_text(errors='ignore'))
scan='\n'.join(scan)
for pat in [r'33,013|33013',r'900/900|\b900\s+(?:independent\s+)?(?:reconstruction\s+)?checks',r'149/149|\b149\s+non[- ]?volatile',r'CodeIP-style available-prefix',r'hybrid[^\n]{0,100}below both']:
 fail(not re.search(pat,scan,re.I),f'stale release statement: {pat}')

# Read-only reconstruction and test receipts are represented and current.
fail(contract['execution']['unit_tests']==13 and contract['execution']['independent_checks']==1470 and contract['execution']['cross_seed_nonvolatile_files']==152,'contract execution counts mismatch')
fail(json.loads((ART/'cross_seed_reproduction.json').read_text())['status']=='PASS','cross-seed audit failed')

# Release-manifest coverage. Excludes itself to avoid circularity.
manifest=ART/'release_manifest.csv'
fail(manifest.exists(),'missing release manifest')
with manifest.open(newline='') as f:rows=list(csv.DictReader(f))
paths={r['path']:r for r in rows}
public=[p for p in ROOT.rglob('*') if p.is_file() and p!=manifest]
fail(set(paths)=={p.relative_to(ROOT).as_posix() for p in public},'release manifest path coverage mismatch')
for p in public:
 rel=p.relative_to(ROOT).as_posix();fail(int(paths[rel]['bytes'])==p.stat().st_size and paths[rel]['sha256']==sha(p),f'manifest mismatch: {rel}')

result={'status':'PASS','root_entries':sorted(p.name for p in ROOT.iterdir()),'public_files':len(public)+1,'manifest_covered_files':len(rows),'main_pages':page['main_pages'],'supplement_pages':page['supplement_pages'],'tests':13,'reconstruction_checks':1470,'cross_seed_nonvolatile_files':152,'bibliography_entries':82,'citation_positions':88,'contract_repairs':'PASS','submission_policy':'HOLD_FOR_HUMAN_AUTHOR_CONFIRMATION_AND_LIVE_PORTAL'}
print(json.dumps(result,indent=2))
