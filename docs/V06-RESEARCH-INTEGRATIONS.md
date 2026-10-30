# Research and service adapters

`ResearchEngine` provides allowlisted public HTTPS fetches, bounded extracts,
source dates when present, retrieval timestamps, byte hashes, citations, Memory
Vault provenance, TTL/query deduplication and explicit conflicting-source comparison.
Only authorized task actors can write into their allowed namespaces. Stale records
need revalidation. HTTP 200 establishes retrieval, never factual VERIFIED status.
Status values: VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, OUTDATED, CONFLICTING.

The host must configure allowed_hosts and usable DNS/proxy/TLS. Private, loopback,
non-HTTPS, secret-bearing and unauthorized destinations are rejected, including
redirects. DNS failures fail closed. Default search is explicitly unavailable;
an injected authorized search adapter can supply results. GitHub repository search
is repository metadata search, not a general current-web search engine.

Use from Python with the actual Hub and task ID:

```python
from agent_hub.research import ResearchEngine
engine = ResearchEngine(hub, {"allowed_hosts": ["docs.python.org"]})
doc = engine.fetch(task_id, "https://docs.python.org/3/", actor="management-director")
```

`GitHubReadAdapter` uses documented REST user/repository/contents/search GETs.
Public repository reads do not authenticate an account; `/user` must succeed before
an AUTHENTICATED claim. `NotionReadAdapter` requires a verified explicit Notion-Version
and secure token environment reference, then uses documented user/page GETs.
`NativeReadAdapter` wraps only host-injected documented read operations; a repository
configuration cannot import arbitrary provider code. Production JSON cannot inject
transport functions. No built-in write endpoints were added.

Figma, Drive, creative/rendering, social publishing, analytics and deployment retain
v0.5 candidate/discovery and approval gates. Without a real supported host tool and
a verified call, they remain unavailable/unconnected; uploaded source packages are
not live integrations. External writes still require the existing exact scoped
approval, verification and ambiguous-outcome reconciliation workflow. No social
content was published, no deployment or trading order was executed in validation.
