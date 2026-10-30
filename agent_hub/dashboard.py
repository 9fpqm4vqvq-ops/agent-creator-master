"""Loopback-only, read-only dashboard. Never constructs a Hub or runs migrations."""
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .monitoring import snapshot
from .security import redact
from .migrations import VERSION


def connect_readonly(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
    if db.execute('PRAGMA user_version').fetchone()[0]!=VERSION:
        db.close();raise ValueError('Migrate the database with matching code before serving the dashboard')
    return db


def make_server(db_path,root,port=8765):
    db_path=Path(db_path);root=Path(root)
    check=connect_readonly(db_path);check.close()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,body,content_type='application/json; charset=utf-8'):
            try:
                self.send_response(status)
                for key,value in {'Content-Type':content_type,'Content-Length':str(len(body)),
                    'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                    'Content-Security-Policy':"default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                    'Referrer-Policy':'no-referrer'}.items():self.send_header(key,value)
                self.end_headers();self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):
                return # Client navigated away; no second response or server failure.
        def do_GET(self):
            allowed={'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}
            host=self.headers.get('Host','')
            origin=self.headers.get('Origin')
            if host not in allowed or origin and origin not in {'http://'+h for h in allowed}:
                self.send(403,b'{"error":"Loopback Host/Origin required"}');return
            route=urlsplit(self.path).path
            try:
                if route.startswith('/api/'):
                    db=connect_readonly(db_path)
                    try:
                        db.execute('BEGIN') # all panels reflect one SQLite read transaction
                        if route=='/api/snapshot':result=snapshot(db,root)
                        elif route.startswith('/api/tasks/') and route[11:].isdigit():
                            identity=int(route[11:]);task=db.execute('SELECT * FROM tasks WHERE id=?',(identity,)).fetchone()
                            if task is None:self.send(404,b'{"error":"Unknown task"}');return
                            from .usage import UsageLedger, BudgetService
                            result={'task':dict(task),'usage':UsageLedger(db).summary(task_id=identity),
                                'invocations':[dict(r) for r in db.execute('SELECT * FROM usage_events WHERE task_id=?',(identity,))],
                                'budget_status':BudgetService(db).evaluate(identity,task['owner'],'0'), 'history':[dict(r,detail=json.loads(r['detail']),refs=json.loads(r['refs'])) for r in db.execute('SELECT * FROM events WHERE task_id=? ORDER BY id',(identity,))]}
                        else:self.send(404,b'{"error":"Unknown endpoint"}');return
                        self.send(200,json.dumps(redact(result)).encode())
                    finally:db.close()
                else:
                    static={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
                    if route not in static:self.send(404,b'{"error":"Not found"}');return
                    filename,ctype=static[route];self.send(200,(root/'dashboard'/filename).read_bytes(),ctype)
            except (ValueError,OSError,sqlite3.Error):self.send(503,b'{"error":"Read-only snapshot unavailable; inspect database version and local files"}')
        def do_POST(self):self.send(405,b'{"error":"Read-only dashboard"}')
        do_PUT=do_POST;do_DELETE=do_POST;do_PATCH=do_POST
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def serve(db_path,root,port=8765):
    server=make_server(db_path,root,port)
    print('Read-only dashboard: http://127.0.0.1:'+str(server.server_port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
