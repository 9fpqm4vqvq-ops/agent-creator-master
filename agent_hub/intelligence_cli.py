"""Small JSON-argument interface for the v0.4 services; no runtime model adapter."""
import json
import time
from .security import redact


def execute(hub,command,action,data):
    if not isinstance(data,dict):raise ValueError('Command data must be a JSON object')
    if command=='usage':
        if action=='estimate':
            from .usage import estimate_cost
            return estimate_cost(**data)
        return getattr(hub.usage,action)(**data)
    if command=='budget':return getattr(hub.budgets,action)(**data)
    if command=='health':return getattr(hub.health,action)(**data)
    if command=='freshness':
        if action=='history':return hub.memory.history(**data)
        return getattr(hub.freshness,action)(**data)
    if command=='research-cache':return getattr(hub.research_cache,action)(**data)
    if command=='improvements':
        if action=='recover':return hub.improvements.rollback(**data,recovery=True)
        return getattr(hub.improvements,action)(**data)
    if command=='scorecards':
        from .monitoring import scorecards
        return scorecards(hub.db)
    if command=='scheduler':
        if action=='list':return hub.scheduler.jobs()
        if action=='history':return [dict(r) for r in hub.db.execute('SELECT * FROM maintenance_runs ORDER BY started_at DESC')]
        if action=='run':
            seconds=data.get('poll_seconds',15)
            if type(seconds) is not int or not 1<=seconds<=60:raise ValueError('poll_seconds must be 1..60')
            print('Explicit local scheduler loop running; Ctrl-C to stop. Only enabled fixed jobs can run.',flush=True)
            try:
                while True:
                    print(json.dumps(redact(hub.scheduler.tick())),flush=True);time.sleep(seconds)
            except KeyboardInterrupt:return {'stopped':True}
        return getattr(hub.scheduler,action)(**data)
    raise ValueError('Unknown intelligence command')
