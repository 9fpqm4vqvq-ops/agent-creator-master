#!/usr/bin/env python3
"""Free local vertical caption-card renderer plus ffprobe technical check.
No network/voice synthesis provided; use user-owned audio when available.
"""
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

def probe(path):
 if not shutil.which('ffprobe'): raise RuntimeError('ffprobe required; install FFmpeg')
 res=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height,codec_name','-of','json',str(path)],capture_output=True,text=True,check=True)
 return json.loads(res.stdout)
def qa(path):
 data=probe(path);streams=data.get('streams',[]);video=next((s for s in streams if s.get('codec_type')=='video'),None)
 problems=[]
 if not video: problems.append('BLOCKER: Missing video stream')
 elif (video.get('width'),video.get('height'))!=(1080,1920): problems.append('HIGH: Expected 1080x1920 vertical video')
 duration=float(data.get('format',{}).get('duration',0) or 0)
 if duration<=0: problems.append('BLOCKER: Invalid duration')
 if duration>180: problems.append('HIGH: exceeds conservative 180-second Shorts target')
 if not any(s.get('codec_type')=='audio' for s in streams): problems.append('NOTICE: No audio stream; human review required')
 h=hashlib.sha256(Path(path).read_bytes()).hexdigest()
 print(json.dumps({'artifact':str(path),'sha256':h,'duration_seconds':duration,'streams':streams,'technical_result':'FAIL' if any(p.startswith(('BLOCKER','HIGH')) for p in problems) else 'PASS_WITH_MANUAL_REVIEW','issues':problems,'human_review_required':['fact checking','copyright/asset licensing','visual artifacts','caption sync/legibility','audio listening','YouTube policies']},indent=2))
 return 1 if any(p.startswith(('BLOCKER','HIGH')) for p in problems) else 0

def render(a):
 if not shutil.which('ffmpeg'): raise RuntimeError('ffmpeg required')
 words=Path(a.script).read_text(encoding='utf8').splitlines()
 lines=[line.strip() for line in words if line.strip()]
 if not lines: raise ValueError('Script has no lines')
 if a.seconds_per_card<1 or a.seconds_per_card>30: raise ValueError('seconds-per-card must be 1..30')
 out=Path(a.output).resolve();out.parent.mkdir(parents=True,exist_ok=True)
 # FFmpeg text overlay via drawtext requires available libfreetype; do not rely on external downloads.
 # Escape drawtext via textfile instead of interpolating user content.
 with tempfile.TemporaryDirectory() as t:
  t=Path(t);parts=[]
  for i,line in enumerate(lines):
   txt=t/f'caption_{i}.txt';txt.write_text(line,encoding='utf8')
   path=t/f'card_{i}.mp4'
   filterstr=f"drawtext=textfile='{txt.as_posix()}':fontcolor=white:fontsize=58:line_spacing=14:x=(w-text_w)/2:y=(h-text_h)/2:fix_bounds=1"
   cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=0x111827:s=1080x1920:r=30','-t',str(a.seconds_per_card),'-vf',filterstr,'-an','-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p',str(path)]
   subprocess.run(cmd,check=True);parts.append(path)
  concat=t/'list.txt';concat.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts))
  cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat)]
  if a.audio:
   cmd+=['-i',str(Path(a.audio).resolve()),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-shortest']
  else: cmd+=['-c','copy']
  cmd+=[str(out)];subprocess.run(cmd,check=True)
 print('Rendered',out,'NOTE: basic caption-card prototype only; manual editorial, licensing and QA review required')
 return qa(out)
def main():
 p=argparse.ArgumentParser();sp=p.add_subparsers(dest='command',required=True)
 r=sp.add_parser('render');r.add_argument('--script',required=True);r.add_argument('--output',required=True);r.add_argument('--audio');r.add_argument('--seconds-per-card',type=float,default=3.5)
 q=sp.add_parser('qa');q.add_argument('--video',required=True)
 a=p.parse_args()
 try: return render(a) if a.command=='render' else qa(Path(a.video))
 except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as e:
  print('ERROR:',e,file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
