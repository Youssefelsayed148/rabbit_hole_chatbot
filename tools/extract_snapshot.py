"""Reproduce this observed build's static bilingual extraction. Standard library only.
Not a general crawler. Use rendered DOM or source/CMS export for future builds.
Usage: python extract_snapshot.py PATH_TO_PUBLIC_APP_BUNDLE OUTPUT_DIRECTORY
Never index the bundle itself: it contains application code and configuration.
"""
import argparse, hashlib, json, re
from pathlib import Path
from datetime import datetime, timezone
BASE='https://darkturquoise-dunlin-447124.hostingersite.com'
EXPECTED=1480320
Q=r'("(?:\\.|[^"\\])*")'

def extract(bundle, out):
 s=Path(bundle).read_text();out=Path(out);out.mkdir(parents=True,exist_ok=True)
 docs=[];stamp=datetime.now(timezone.utc).isoformat();build=hashlib.sha256(s.encode()).hexdigest()
 def add(slug,path,lang,title,lines,status='observed',method='public_bundle_literals',note=''):
  text='\n\n'.join(lines)
  docs.append(dict(id=slug+'-'+lang,source_url=BASE+path,language=lang,title=title,text=text,content_type='policy' if path in ['/terms','/refund','/privacy'] else 'brand' if path=='/brand-story' else 'support',extracted_at=stamp,source_updated_at='2026-04-26' if path in ['/terms','/refund','/privacy'] else None,content_hash=hashlib.sha256(text.encode()).hexdigest(),build_hash=build,verification_status=status,extraction_method=method,notes=note))
 for name,nxt,path in [('uJ','dJ','/terms'),('dJ','fJ','/refund'),('fJ','bJ','/privacy')]:
  start=s.index(name+'=');end=s.index(nxt+'=',start+1);part=s[start:end]
  pairs=re.findall(r'children:\w+==="ar"\?'+Q+':'+Q,part)
  # Policy ends at its explicit update label; later components must not leak in.
  stop=next(i+1 for i,p in enumerate(pairs) if json.loads(p[1]).startswith('Last Updated:'))
  pairs=pairs[:stop]
  assert len(pairs)==11,(name,len(pairs))
  for col,lang in [(0,'ar'),(1,'en')]:
   lines=[json.loads(p[col]) for p in pairs]
   add(path[1:],path,lang,lines[0],lines,'render_verified' if lang=='en' else 'source_extracted','public_bundle_literals; English cross-checked in browser','Arabic is source text, not machine translation; review Arabic rendering before launch.')
 start=s.index('kQ=');end=s.index('];return',start);part=s[start:end]
 pattern=r'type:"(header|paragraph)",content:l==="ar"\?(?:c\.jsx\(c\.Fragment,\{children:)?'+Q+r'(?:\}\))?:'+Q
 pairs=re.findall(pattern,part)
 assert len(pairs)==10,len(pairs)
 for col,lang in [(1,'ar'),(2,'en')]:
  lines=[json.loads(p[col]) for p in pairs]
  add('brand-story','/brand-story',lang,'Rabbit Hole Story',lines[:8],'render_verified' if lang=='en' else 'source_extracted')
  add('collection-story','/brand-story',lang,'Rabbit Hole Collection',lines[8:],'render_verified' if lang=='en' else 'source_extracted',note='Collection story modal on brand-story page, not a product catalogue.')
 # Supplementary product modal text was seen in application source only.
 part=s[690000:s.index('ik=')]
 pairs=re.findall(r'(?:children|content):\w+==="ar"\?'+Q+':'+Q,part)
 for col,lang in [(0,'ar'),(1,'en')]:
  lines=list(dict.fromkeys(json.loads(p[col]) for p in pairs if len(json.loads(p[1]))>75 and not any(x in json.loads(p[1]) for x in ['Enter your email','priority list'])))
  add('product-support-draft','/collection',lang,'Product support modal copy',lines,'needs_review',note='Not confirmed in rendered product view. Shipping and payment statements need owner confirmation; refund page takes precedence. Do not place into production index yet.')
 for lang in ['en','ar']:
  add('contact','/',lang,'Public business contact',['Rabbit Hole','info@rabbithole.ae','Dubai, UAE'],'render_verified','public_footer','Business location only; not a verified street address, store address, phone number, or opening hours.')
 (out/'documents.jsonl').write_text(''.join(json.dumps(d,ensure_ascii=False)+'\n' for d in docs))
 chunks=[]
 for d in docs:
  if d['verification_status']=='needs_review':continue
  lines=d['text'].split('\n\n')
  if d['content_type']=='policy':
   sections=[(lines[0],lines[1])]+[(lines[i],lines[i+1]) for i in range(2,10,2)]
  elif d['content_type']=='brand':sections=[(lines[i],lines[i+1]) for i in range(0,len(lines),2)]
  else:sections=[(d['title'],d['text'])]
  for i,(heading,text) in enumerate(sections):
   c={k:v for k,v in d.items() if k!='text'}
   c.update(chunk_id=d['id']+'-'+str(i+1),heading=heading,text=heading+'\n'+text,parent_document_id=d['id'])
   chunks.append(c)
 (out/'chunks.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in chunks))
 (out/'knowledge_base.md').write_text('# Rabbit Hole website content snapshot\n\nExtracted '+stamp+'\n\n'+ '\n\n'.join('## '+d['title']+' ('+d['language']+')\n\nSource: '+d['source_url']+'\n\nStatus: '+d['verification_status']+'\n\n'+d['text'] for d in docs))
 (out/'manifest.json').write_text(json.dumps(dict(base_url=BASE,extracted_at=stamp,documents=len(docs),chunks=len(chunks),build_sha256=build,product_catalogue_status='not_extracted: API request returned HTTP 403',missing=['catalogue','product detail records','artwork content','live prices','stock','size chart','shipping destinations/fees/delivery SLA','video/audio-only content']),indent=2))
 print(json.dumps(dict(documents=len(docs),chunks=len(chunks),languages=['en','ar'],draft_documents=2)))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('bundle');p.add_argument('output');a=p.parse_args();extract(a.bundle,a.output)
