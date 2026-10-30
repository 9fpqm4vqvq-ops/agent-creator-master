#!/usr/bin/env python3
"""Shorts Growth Lab deterministic starter utilities. Python stdlib only."""
import argparse, csv, datetime as dt, json, os, sqlite3, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data'/'shortslab.db'
def connect():
 DB.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(DB)
 c.execute('PRAGMA foreign_keys=ON')
 c.executescript("""CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, title TEXT NOT NULL, rationale TEXT NOT NULL, evidence TEXT NOT NULL, next_review TEXT);
 CREATE TABLE IF NOT EXISTS experiments(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, name TEXT NOT NULL, hypothesis TEXT NOT NULL, metric TEXT NOT NULL, target TEXT NOT NULL, status TEXT DEFAULT 'proposed', result TEXT);
 CREATE TABLE IF NOT EXISTS analytics(video_id TEXT NOT NULL, observation_date TEXT NOT NULL, published_at TEXT, views INTEGER, engaged_views INTEGER, subscribers_gained INTEGER, revenue_usd REAL, average_view_duration_seconds REAL, source TEXT NOT NULL, PRIMARY KEY(video_id,observation_date,source));""")
 return c
def utc(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def niche_score(item):
 keys=['demand','competition','repeatability','monetization','originality','difficulty']
 for k in keys:
  if k not in item or isinstance(item[k],bool) or not isinstance(item[k],(int,float)) or not 0<=item[k]<=5: raise ValueError(f'{k} must be numeric from 0 to 5')
 # Weighted: positive 0.25,0.20,0.20,0.15; reverse competition 0.10 and difficulty 0.10
 return round(20*(.25*item['demand']+.20*item['repeatability']+.20*item['monetization']+.15*item['originality']+.10*(5-item['competition'])+.10*(5-item['difficulty'])),2)
def cmd_score(a):
 rows=json.loads(Path(a.input).read_text(encoding='utf8'))
 if not isinstance(rows,list): raise ValueError('JSON must be an array')
 out=sorted([dict(x,score=niche_score(x)) for x in rows],key=lambda x:x['score'],reverse=True)
 print(json.dumps({'warning':'Scores are subjective inputs; no validation of evidence is performed','weights':{'demand':.25,'repeatability':.20,'monetization':.20,'originality':.15,'low_competition':.10,'low_difficulty':.10},'results':out},indent=2))
def cmd_init(a):
 with connect() as c: pass
 print('Initialized',DB)
def cmd_decision(a):
 with connect() as c:
  cur=c.execute('INSERT INTO decisions(created_at,title,rationale,evidence,next_review) VALUES(?,?,?,?,?)',(utc(),a.title,a.rationale,a.evidence,a.next_review))
  print('Recorded decision',cur.lastrowid)
def cmd_experiment(a):
 with connect() as c:
  cur=c.execute('INSERT INTO experiments(created_at,name,hypothesis,metric,target) VALUES(?,?,?,?,?)',(utc(),a.name,a.hypothesis,a.metric,a.target))
  print('Registered experiment',cur.lastrowid)
def cmd_result(a):
 with connect() as c:
  cur=c.execute('UPDATE experiments SET status=?,result=? WHERE id=?',(a.status,a.result,a.id))
  if not cur.rowcount: raise ValueError('No experiment with that ID')
  print('Updated experiment',a.id)
def nonnegative_int(value):
 if value is None or str(value).strip()=='': return None
 x=int(value)
 if x<0: raise ValueError('negative count')
 return x
def cmd_import(a):
 rows=list(csv.DictReader(open(a.csv,newline='',encoding='utf8-sig')))
 required={'video_id','observation_date','published_at','views','engaged_views','subscribers_gained','revenue_usd','average_view_duration_seconds'}
 if not rows or not required.issubset(rows[0]): raise ValueError('CSV missing required columns or rows')
 parsed=[]
 for r in rows:
  dt.date.fromisoformat(r['observation_date']);dt.date.fromisoformat(r['published_at'])
  counts=[nonnegative_int(r[x]) for x in ('views','engaged_views','subscribers_gained')]
  rev=float(r['revenue_usd']) if r['revenue_usd'] else None
  dur=float(r['average_view_duration_seconds']) if r['average_view_duration_seconds'] else None
  if rev is not None and rev<0: raise ValueError('negative revenue')
  if dur is not None and dur<0: raise ValueError('negative duration')
  parsed.append((r['video_id'],r['observation_date'],r['published_at'],*counts,rev,dur,a.source))
 with connect() as c:
  c.executemany('INSERT OR REPLACE INTO analytics(video_id,observation_date,published_at,views,engaged_views,subscribers_gained,revenue_usd,average_view_duration_seconds,source) VALUES(?,?,?,?,?,?,?,?,?)',parsed)
 print(f'Imported {len(parsed)} rows (source={a.source}). Note: sample records are not real performance.')
def cmd_summary(a):
 with connect() as c:
  c.row_factory=sqlite3.Row
  print(json.dumps({'decisions':[dict(x) for x in c.execute('SELECT * FROM decisions ORDER BY id DESC LIMIT 15')], 'experiments':[dict(x) for x in c.execute('SELECT * FROM experiments ORDER BY id DESC LIMIT 15')], 'analytics':[dict(x) for x in c.execute('SELECT * FROM analytics ORDER BY observation_date DESC LIMIT 25')]},indent=2))
def cmd_research(a):
 key=os.getenv('YOUTUBE_API_KEY')
 if not key: raise RuntimeError('YOUTUBE_API_KEY is absent; set it in environment. Public research skipped.')
 params=urllib.parse.urlencode({'part':'snippet','q':a.query,'type':'video','videoDuration':'short','maxResults':a.max_results,'key':key})
 request=urllib.request.Request('https://www.googleapis.com/youtube/v3/search?'+params,headers={'User-Agent':'ShortsGrowthLab/0.1'})
 with urllib.request.urlopen(request,timeout=20) as f: data=json.load(f)
 results=[{'video_id':x.get('id',{}).get('videoId'),'title':x.get('snippet',{}).get('title'),'channel':x.get('snippet',{}).get('channelTitle'),'published_at':x.get('snippet',{}).get('publishedAt')} for x in data.get('items',[])]
 print(json.dumps({'search_query':a.query,'retrieved_at':utc(),'caveats':['videoDuration=short filters duration, not guaranteed actual Shorts classification','search is sampled and ranking-biased','No private retention or revenue access'],'videos':results},indent=2))
def parser():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
 s.add_parser('init').set_defaults(fn=cmd_init)
 q=s.add_parser('score');q.add_argument('--input',required=True);q.set_defaults(fn=cmd_score)
 q=s.add_parser('decision');q.add_argument('--title',required=True);q.add_argument('--rationale',required=True);q.add_argument('--evidence',required=True);q.add_argument('--next-review');q.set_defaults(fn=cmd_decision)
 q=s.add_parser('experiment');q.add_argument('--name',required=True);q.add_argument('--hypothesis',required=True);q.add_argument('--metric',required=True);q.add_argument('--target',required=True);q.set_defaults(fn=cmd_experiment)
 q=s.add_parser('result');q.add_argument('--id',type=int,required=True);q.add_argument('--status',choices=['proposed','running','completed','cancelled'],required=True);q.add_argument('--result',required=True);q.set_defaults(fn=cmd_result)
 q=s.add_parser('analytics-import');q.add_argument('--csv',required=True);q.add_argument('--source',default='manual_csv');q.set_defaults(fn=cmd_import)
 s.add_parser('summary').set_defaults(fn=cmd_summary)
 q=s.add_parser('research');q.add_argument('--query',required=True);q.add_argument('--max-results',type=int,default=5);q.set_defaults(fn=cmd_research)
 return p
if __name__=='__main__':
 a=parser().parse_args()
 try: a.fn(a)
 except (ValueError,RuntimeError,OSError) as e:
  print('ERROR:',e,file=sys.stderr);sys.exit(2)
