#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, os, re, subprocess, sys, tempfile, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'paper'; A=ROOT/'artifact'

def fail(msg): raise SystemExit('RELEASE VERIFICATION FAILED: '+msg)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def run(*cmd):
 try:return subprocess.run(cmd,text=True,capture_output=True,check=True).stdout
 except (FileNotFoundError,subprocess.CalledProcessError) as e: fail('command failed: '+' '.join(cmd)+'\n'+getattr(e,'stderr',''))
def pdf_pages(p):
 m=re.search(r'^Pages:\s+(\d+)',run('pdfinfo',str(p)),re.M)
 if not m: fail('cannot read page count: '+str(p))
 return int(m.group(1))
def pdf_text(p): return run('pdftotext',str(p),'-')
def parse_bib(text): return re.findall(r'^@\w+\{\s*([^,]+),',text,re.M)
def cite_keys(text):
 cmds=re.findall(r'\\cite(?:\[[^]]*\])?\{([^}]+)\}',text)
 return cmds,[x.strip() for c in cmds for x in c.split(',') if x.strip()]
def line_numbers(pdf):
 xml=run('pdftotext','-bbox-layout',str(pdf),'-')
 root=ET.fromstring(xml)
 ns={'x':'http://www.w3.org/1999/xhtml'}
 allnums=[];per=[]
 for page in root.findall('.//x:page',ns):
  width=float(page.attrib['width']); nums=[]
  for word in page.findall('.//x:word',ns):
   txt=''.join(word.itertext()).strip()
   if not re.fullmatch(r'\d{1,5}',txt):continue
   x0=float(word.attrib['xMin']);x1=float(word.attrib['xMax']);y0=float(word.attrib['yMin'])
   if y0<35 or y0>755:continue
   if x1<52 or x0>width-52:nums.append(int(txt))
  nums=sorted(set(nums));per.append(nums);allnums.extend(nums)
 return allnums,per
# Root contract.
expected={'paper','artifact','research-plan.md','CURRENT-STATE.md'}
actual={p.name for p in ROOT.iterdir()}
if actual!=expected: fail(f'root entries {sorted(actual)} != {sorted(expected)}')
# No links, caches, nested archives, backups, or alternate paper PDFs.
for p in ROOT.rglob('*'):
 if p.is_symlink():fail('symbolic link: '+str(p.relative_to(ROOT)))
 if p.is_dir() and p.name in {'__pycache__','.git','.pytest_cache','.mypy_cache'}:fail('cache directory: '+str(p.relative_to(ROOT)))
 if p.is_file():
  rel=p.relative_to(ROOT).as_posix();low=p.name.lower()
  if p.suffix in {'.pyc','.pyo','.aux','.log','.blg','.bbl','.out','.fls','.fdb_latexmk','.zip'}:fail('generated or nested archive: '+rel)
  if re.search(r'(before|backup|old|draft|round|revision|version[-_]?\d)',low):fail('historical filename: '+rel)
pdfs=sorted(p.name for p in P.glob('*.pdf'))
if pdfs!=['main.pdf','online-supplement.pdf']:fail('paper PDFs must be main.pdf and online-supplement.pdf only: '+repr(pdfs))
# Required files.
for rel in ['paper/main.tex','paper/online-supplement.tex','paper/references.bib','paper/acmart.cls','paper/ACM-Reference-Format.bst','paper/main.pdf','paper/online-supplement.pdf','artifact/results/recheck_report.json','artifact/reference_final_verification.json','artifact/reference_metadata_audit.json','artifact/generator_configuration_audit.json','artifact/novelty_landscape_audit.json','artifact/author_metadata_audit.json']:
 if not (ROOT/rel).is_file():fail('missing '+rel)
main=(P/'main.tex').read_text(encoding='utf-8');supp=(P/'online-supplement.tex').read_text(encoding='utf-8');bib=(P/'references.bib').read_text(encoding='utf-8')
# Template and source integrity.
for name,src in [('main',main),('supplement',supp)]:
 m=re.search(r'\\documentclass\[([^]]+)\]\{acmart\}',src)
 if not m or set(x.strip() for x in m.group(1).split(','))!={'manuscript','screen','review'}:fail(name+' documentclass is not manuscript,screen,review')
 if 'authorsperrow=1' not in src:fail(name+' lacks authorsperrow=1')
 banned=[r'\\usepackage\{geometry\}',r'\\geometry\{',r'\\textwidth\s*=',r'\\textheight\s*=',r'\\oddsidemargin\s*=',r'\\evensidemargin\s*=',r'\\topmargin\s*=',r'\\linespread',r'\\setstretch',r'\\fontsize',r'\\vspace\s*\{\s*-']
 for pat in banned:
  if re.search(pat,src):fail(name+' contains forbidden layout override: '+pat)
 for token in [r'\acmDOI{',r'\acmVolume{',r'\acmNumber{',r'\acmArticle{',r'\copyrightyear{',r'\received{']:
  if token in src:fail(name+' contains unassigned production metadata '+token)
# Six positions, three named, three invisible reserves.
for name,src in [('main',main),('supplement',supp)]:
 if len(re.findall(r'\\author\{',src))!=6:fail(name+' must contain six author declarations')
 for person in ['Haoyi Zhang','Huaijin Ran','Xunzhu Tang']:
  if src.count('\\author{'+person+'}')!=1:fail(name+' author mismatch: '+person)
 if src.count(r'\author{\mbox{\phantom{Reserved Author}}}')!=3:fail(name+' reserved-author count mismatch')
 if src.count(r'\correspondingauthor')!=1:fail(name+' corresponding-author count mismatch')
 if src.index(r'\author{Huaijin Ran}')>src.index(r'\correspondingauthor') or src.index(r'\correspondingauthor')>src.index(r'\author{Xunzhu Tang}'):fail(name+' corresponding marker not bound to Huaijin Ran')
 for email in ['hyeliozhang@gmail.com','huaijin003@e.ntu.edu.sg','realdanieltang@gmail.com']:
  if src.count(email)!=1:fail(name+' email mismatch: '+email)
 for old in ['Qihan Jin','Md Maruf Hasan','seventeen17510@gmail.com']:
  if old in src:fail(name+' contains superseded author metadata: '+old)
# PDF integrity, page size, fonts, visible text.
for pdf in [P/'main.pdf',P/'online-supplement.pdf']:
 if shutil:=__import__('shutil'):
  if shutil.which('qpdf'):run('qpdf','--check',str(pdf))
 info=run('pdfinfo',str(pdf))
 if 'Page size:       612 x 792 pts (letter)' not in info:fail('non-Letter page size: '+pdf.name)
 font=run('pdffonts',str(pdf)).splitlines()[2:]
 if not font:fail('no fonts: '+pdf.name)
 for line in font:
  cols=line.split()
  if len(cols)>=8 and (cols[4]!='yes' or cols[5]!='yes' or cols[6]!='yes'):fail('font not embedded/subset/Unicode: '+line)
 text=pdf_text(pdf)
 for bad in ['Reserved Author','Reserved Institution','ChatGPT','OpenAI','Codex','Web Pro','/mnt/data','/home/oai','Author Placeholder']:
  if bad.casefold() in text.casefold():fail(pdf.name+' exposes '+bad)
 if 'https://doi.org/' in text and not re.search(r'https://doi\.org/\S+',text):fail(pdf.name+' exposes empty DOI prefix')
main_text=pdf_text(P/'main.pdf');supp_text=pdf_text(P/'online-supplement.pdf')
for visible in ['Haoyi Zhang','Huaijin Ran','Xunzhu Tang','Nanyang Technological University','University of Luxembourg']:
 if visible not in main_text:fail('main PDF missing '+visible)
if 'Abstract' not in main_text[:12000]:fail('abstract not on first-page text region')
# Line numbers continuous.
nums,per=line_numbers(P/'main.pdf')
if not nums or nums!=list(range(1,max(nums)+1)):fail('review line numbers are missing or discontinuous')
if len(per)!=pdf_pages(P/'main.pdf') or any(not x for x in per):fail('one or more main-PDF pages lack line numbers')
# Bibliography/citations.
bibkeys=parse_bib(bib);cmds,keys=cite_keys(main)
if len(cmds)!=len(keys):fail('multi-key citation command detected')
if set(keys)!=set(bibkeys):fail('citation/bibliography set mismatch')
if len(bibkeys)!=len(set(bibkeys)):fail('duplicate bibliography key')
ref=json.loads((A/'reference_final_verification.json').read_text())
if ref.get('verdict')!='PASS' or ref.get('entries')!=len(bibkeys):fail('reference final verification failed')
meta=json.loads((A/'reference_metadata_audit.json').read_text())
if meta.get('verdict')!='PASS':fail('reference metadata audit failed')
# Scientific result checks.
rep=json.loads((A/'results/recheck_report.json').read_text())
if rep.get('status')!='PASS' or rep.get('failures'):fail('scientific reconstruction failed')
if json.loads((A/'generator_configuration_audit.json').read_text()).get('status')!='PASS':fail('generator configuration sensitivity missing')
if json.loads((A/'novelty_landscape_audit.json').read_text()).get('verdict')!='PASS':fail('novelty landscape audit failed')
# Reader-facing prompt/process traces.
for rel,text in [('main.tex',main),('online-supplement.tex',supp)]:
 for bad in ['ChatGPT','OpenAI','Codex','Web Pro','chain of thought','/mnt/data','/home/oai']:
  if bad.casefold() in text.casefold():fail(rel+' contains private process trace '+bad)
# Release manifest if present.
manifest=A/'release_manifest.csv'
if manifest.exists():
 rows=list(csv.DictReader(manifest.open(encoding='utf-8')))
 expected_paths={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and p!=manifest}
 seen={r['path'] for r in rows}
 if seen!=expected_paths:fail('release manifest path set mismatch')
 for r in rows:
  p=ROOT/r['path']
  if int(r['bytes'])!=p.stat().st_size or r['sha256']!=sha(p):fail('release manifest mismatch: '+r['path'])
summary={'status':'PASS','root_entries':sorted(actual),'public_files':sum(1 for p in ROOT.rglob('*') if p.is_file()),'main_pages':pdf_pages(P/'main.pdf'),'supplement_pages':pdf_pages(P/'online-supplement.pdf'),'line_number_first':nums[0],'line_number_last':nums[-1],'bibliography_entries':len(bibkeys),'citation_commands':len(cmds),'reconstruction_checks':rep.get('checks'),'scientific_results_sha256':rep.get('scientific_results_sha256'),'named_authors':3,'reserved_author_positions':3}
print(json.dumps(summary,indent=2))
