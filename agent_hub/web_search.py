"""General web search through a trusted host's documented search tool.

No scraping, guessed endpoint, credential discovery or production mock fallback.
The host supplies the callback; downloadable JSON cannot import or execute one.
"""
from .legacy import required
from .security import redact
from .research import ResearchUnavailable

class NativeWebSearchAdapter:
 provider='host-general-web-search'
 def __init__(self,invoke,evidence_kind='LIVE_NATIVE_TOOL'):
  if not callable(invoke):raise ValueError('A documented authenticated host search callback is required')
  if evidence_kind not in {'LIVE_NATIVE_TOOL','SIMULATED'}:raise ValueError('Declare actual host versus test evidence')
  self.invoke=invoke;self.evidence_kind=evidence_kind
 def __call__(self,query):
  if not isinstance(query,str) or not query.strip() or len(query)>500 or redact(query)!=query:raise ValueError('Use a bounded non-secret public search query')
  result=self.invoke({'query':query,'limit':10})
  if not isinstance(result,dict) or not isinstance(result.get('results'),list):raise ResearchUnavailable('SEARCH BLOCKED — host did not return documented result records')
  required(result.get('reference'),'Actual host search invocation reference')
  return {'provider':self.provider,'results':result['results'][:10],'reference':result['reference'],
   'scope':'GENERAL_WEB_SEARCH_RESULTS_NOT_FACT_VERIFICATION','evidence_kind':self.evidence_kind}

class UnconfiguredWebSearch:
 provider='unconfigured-general-web-search'
 def __call__(self,query):raise ResearchUnavailable('SEARCH BLOCKED — configure a supported authenticated general web search callback')
