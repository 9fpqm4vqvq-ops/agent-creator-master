#!/usr/bin/env python3
"""Optional YouTube Data API public search using standard library. No API key bundled."""
import argparse, json, os, sys, urllib.parse, urllib.request

def main():
    p=argparse.ArgumentParser(description='Public YouTube discovery; demand clues only, not earnings evidence')
    s=p.add_subparsers(dest='command', required=True)
    q=s.add_parser('search'); q.add_argument('--query',required=True);q.add_argument('--limit',type=int,default=10)
    a=p.parse_args()
    key=os.getenv('YOUTUBE_API_KEY')
    if not key:
        print('YOUTUBE_API_KEY missing; integration disabled',file=sys.stderr);return 2
    if not 1<=a.limit<=50: p.error('--limit must be between 1 and 50')
    params=urllib.parse.urlencode({'part':'snippet','type':'video','q':a.query,'maxResults':a.limit,'key':key})
    url='https://www.googleapis.com/youtube/v3/search?'+params
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'IOI-research-starter/0.1'})
        with urllib.request.urlopen(req,timeout=15) as resp: data=json.load(resp)
        cleaned=[{'video_id':x.get('id',{}).get('videoId'), 'title':x.get('snippet',{}).get('title'), 'channel':x.get('snippet',{}).get('channelTitle'), 'published_at':x.get('snippet',{}).get('publishedAt')} for x in data.get('items',[])]
        print(json.dumps({'query':a.query,'items':cleaned,'caution':'Search results alone cannot validate demand or income.'},indent=2,ensure_ascii=False));return 0
    except Exception as e:
        print('YouTube API call failed ('+type(e).__name__+'); check key, network and quota',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
