# Runtime connector capability registry and action safeguards

The registry stores provider/type, runtime identity, observed operations and kinds,
permission evidence, authentication status, required approvals, documented rates/cost
limits, last successful test, limitations and evidence kind. Candidate names are
NOT_DISCOVERED; a plugin config is not a connection. Nothing auto-connects on startup.

States: NOT_DISCOVERED, AVAILABLE_NOT_CONNECTED, CONNECTED, TESTED_READ, TESTED_WRITE,
READ_ONLY, FAILED, DISABLED. The tested read path normally reaches TESTED_READ/READ_ONLY,
which is stronger evidence than an untested CONNECTED label. No config-only API sets it.

## Discovery in the actual runtime

An authenticated Claude host discovers its currently available tools with its native
capability/tool search. Supply that actual listing and invocation reference to
`connectors discover_tools`, for example:

```json
{
  "runtime_id":"ACTUAL_SESSION_ID",
  "evidence_reference":"ACTUAL_TOOL_LIST_REFERENCE",
  "descriptors":[
    {"provider":"ACTUAL_PROVIDER","connector_type":"MCP","name":"ACTUAL_READ_TOOL","kind":"read"}
  ]
}
```

Operation kinds: read, write, publish, deploy, message, delete, paid-generation.
Inspect the actual schema/description; do not infer write/publish authority from a
name. Single-provider `discover` additionally accepts operations, evidence_reference,
rate_limits, cost_limits, limitations and evidence_kind. Full discovery invalidates
providers absent from the observed runtime. Rediscovery clears old auth/permission
claims. SIMULATED listings remain explicitly marked and are never live account proof.
Historical external actions retain their original evidence kind.

The Python hub cannot enumerate tools inside a different Claude/MCP process by
reading a config. This boundary is intentional. ToolSearch/listing references and
local role names are operator attestations, not a cryptographic identity service.
The build session's GitHub access does not configure the user's Claude Code runtime.
Figma, Higgsfield, Hyperframes, social APIs, Drive, Notion, generation and deployment
providers are candidates until actual current runtime evidence proves availability.

## Configured adapter boundary

No provider SDK/client, secret or arbitrary remote command is bundled. A trusted host
supplies a callable `adapter(operation, arguments, context)` that invokes the actual
native tool, respects its schema/host permissions, and returns the actual tool result.
The function is injected in Python, not loaded/executed from a package or JSON file.

Use CapabilityRegistry.test_read with a harmless authorized nonconsequential read.
It invokes the adapter and requires ok=true, authenticated=true and an actual reference.
Only returned/documented granted_operations from the discovered set gain GRANTED;
a read success never automatically grants write/publish. Tests persist with evidence
kind. Connection/permission observations expire after an hour for action selection.
No paid generation or account write is permitted as a connection test.

`connectors plan` accepts runtime_id, provider and operation. It explains readiness or
returns a local artifact/production/deployment-brief fallback. Missing access is not
fabricated success. A library function being available is not a configured runtime bridge.

## Exact action authority and independent QA

Create a separate Management-reviewed action task, recall/preflight/start and reserve
its forecast in the existing AI ledger. Authorize only a real scoped user request:
connectors authorize data contains task_id, runtime_id, provider, operation,
subject_hash (SHA-256), destination, exact arguments, reference, maximum_usd and optional
valid_minutes (1–1440). The connector must already have current auth/permission evidence.
Never store credentials, signed secrets or hidden reasoning in arguments.

Authority is bound to task, provider/runtime, operation, destination/account, content/
artifact hash, complete argument hash, explicit cost ceiling and expiry. Execution
checks the current task/instruction snapshot, connection and reservation. It consumes
approval once and persists intent before calling the adapter. One external action
can run per task invocation. Duplicate/ambiguous same-subject operations are blocked.
Local caps cannot force a provider's billing hard cap or stop an external session.

Publishing additionally requires the exact unchanged independently approved content,
Social task/project, original copy/asset/calendar payload and publish permission.
Deployment requires the exact independently approved Web project, artifact hashes,
project action task, deployment payload and deploy permission. The guards also apply
to direct CapabilityRegistry.execute calls; task authorization cannot bypass QA.
Other writes/messages/paid generation still need exact authority and actual tool access.
Generating artifacts for QA is distinct from publication/deployment of those artifacts.

Successful output requires ok=true, verified=true and an actual result reference.
Store the receipt and any supplied usage. Unknown telemetry stays UNKNOWN; rejected
telemetry cannot erase the external receipt. Simulated usage is estimated/unknown.
A SIMULATED adapter never becomes a live content publication. This was exercised
with fixtures; no real provider writes were attempted during development.

If a transport/result is ambiguous, status becomes UNKNOWN_NEEDS_RECONCILIATION.
Do not blindly retry with another approval, edit the in-flight subject or assume no
side effect. CapabilityRegistry.reconcile invokes a currently permitted read-only
adapter, requiring authenticated exact-subject proof and reference. NOT_APPLIED
permits a new explicitly authorized attempt; APPLIED/PUBLISHED/SCHEDULED preserves
verified evidence. Unknown results remain unresolved. Content/Vault history is retained.
Provider-specific idempotency/receipt verification is the host adapter's responsibility;
context includes an action_id/idempotency_key, but not all providers support that key.

## Not yet connected

Authenticated Claude native delegation/independent model QA, Figma design editing,
Higgsfield, Hyperframes renderer/FFmpeg workflow, social account scheduling/publishing,
account analytics, mobile SDK builds, deployment platforms, Notion and paid provider
billing controls were not connected or validated live. Existing Markdown projection
and standard-library local tools remain usable. Pin/research/install optional tooling
only through the reviewed change workflow with actual service permissions and costs.

Project/content approval packets must belong to the same project/campaign and its
owning department, and record the actual subject authors; another department's
completed generic QA task cannot supply the specialized approval link.
