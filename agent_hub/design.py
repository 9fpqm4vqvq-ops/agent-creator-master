"""Read-only search of the supplied UI/UX CSV data; recommendations, never current facts."""
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from .legacy import required

DOMAINS={'ux':'ux-guidelines.csv','style':'styles.csv','color':'colors.csv','typography':'typography.csv','web':'app-interface.csv','chart':'charts.csv','product':'products.csv','landing':'landing.csv','icons':'icons.csv'}


def search(root,query,domain='ux',stack=None,limit=5):
    required(query,'Design research query')
    if type(limit) is not int or not 1<=limit<=20:raise ValueError('Design result limit must be 1..20')
    data=Path(root)/'vendor/supplementary/ui-ux-pro-max-skill/data'
    if stack:
        allowed={p.stem for p in (data/'stacks').glob('*.csv')}
        if stack not in allowed:raise ValueError('Requested stack is not present in the supplied dataset')
        filename='stacks/'+stack+'.csv'
    else:
        if domain not in DOMAINS:raise ValueError('Unknown local design domain')
        filename=DOMAINS[domain]
    path=data/filename
    if not path.is_file() or not path.resolve().is_relative_to(data.resolve()):raise ValueError('Supplied design dataset unavailable')
    expected=json.loads((Path(root)/'registry/supplementary-data.json').read_text())['files'].get(str(path.relative_to(Path(root))))
    if expected!=hashlib.sha256(path.read_bytes()).hexdigest():raise ValueError('Supplied design data changed after review; stage and verify the update first')
    tokens=set(re.findall(r'\w+',query.casefold()))
    with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    indexed=[(row,re.findall(r'\w+',' '.join(str(v) for v in row.values()).casefold())) for row in rows]
    scores=[]
    for row,words in indexed:
        score=sum(math.log(1+len(indexed)/(1+sum(token in w for _,w in indexed)))*(words.count(token)/(words.count(token)+1.2)) for token in tokens if token in words)
        if score:scores.append({'score':round(score,5),'guidance':row})
    scores.sort(key=lambda r:-r['score'])
    return {'query':query,'domain':domain,'stack':stack,'source':str(path.relative_to(Path(root))),
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'results':scores[:limit],'matches':len(scores),
        'classification':'ARCHIVED_GUIDANCE_UNVERIFIED_CURRENTNESS',
        'note':'Actual supplied data, not live design research. Verify context, accessibility and dependency/version claims before adopting; no framework is selected by default.'}
