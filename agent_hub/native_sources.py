"""Public source retrieval delegated to an access-checked native host connector.

Default HTTP DNS checks remain unchanged. Native callbacks must use their host's
own destination/access checks; this class grants no networking or credentials.
"""
from .research import PublicHTTPFetcher,ResearchUnavailable
from .legacy import required

class NativeSourceAdapter:
 provider='host-public-source'
 def __init__(self,allowed_hosts,invoke,evidence_kind='LIVE_NATIVE_TOOL'):
  if not callable(invoke):raise ValueError('Actual access-checked host retrieval callback required')
  if evidence_kind not in {'LIVE_NATIVE_TOOL','SIMULATED'}:raise ValueError('Declare actual versus test provenance')
  self.policy=PublicHTTPFetcher(allowed_hosts);self.invoke=invoke;self.evidence_kind=evidence_kind
 def validate_url(self,url):return self.policy.validate_url(url,check_dns=False)
 def __call__(self,url):
  url=self.validate_url(url);response=self.invoke(url)
  if not isinstance(response,dict) or response.get('status')!=200:raise ResearchUnavailable('Native host source retrieval unavailable')
  required(response.get('reference'),'Actual access-checked source tool receipt')
  final=self.validate_url(response.get('url',url))
  return dict(response,url=final,evidence_kind=self.evidence_kind)
