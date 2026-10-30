# Local Memory Vault Architecture

SQLite is the system of record. The task database contains an append-only-by-API
operational event log, task histories, skill metadata/usage, knowledge records and
incremental synchronization queues. Direct SQL access is trusted operator access;
there is no cryptographic audit-log immutability or multiuser authentication.

Namespaces: management, income, ecommerce, trading, shorts, research, quality, shared.
Master and Management can coordinate across namespaces. Department principals can
read/write their own namespace and read shared records. QA can read across namespaces
but write only quality. A caller cannot assert an unknown principal or namespace.
These are local application ACLs; shell access can bypass them and must remain guarded
by the host. Do not expose this CLI as a multiuser network service.

## Knowledge and task memory

Records use stable UUIDs, revisions, content hashes, confidence, timestamps, source
references, owner and optional task ID. Verified facts need dated verified source
records; approval is an operator attestation, not semantic verification of the URL.
Store findings, concise decisions, procedures, reusable solutions, failures and
lessons. The API drops hidden-reasoning keys and redacts recognized credential keys,
assignment strings, known token formats and private-key blocks. Redaction is best-effort defense, not permission to submit secrets. Never put passwords or private
reasoning in requests, memory or artifacts in the first place.

Before preflight, recall relevant past outcomes. Record the query and retrieved IDs.
Current user instructions, permissions and current evidence always outrank memory.
After QA PASS, save the approved summary, byte hashes, sources, limitations and only
lessons actually supplied. Do not manufacture reusable lessons or token savings.

## Provider interface

`MemoryProvider.write(record, expected_hash)` defines idempotent projection writes.
SQLiteProvider delegates validated reads/writes to MemoryVault. MarkdownVaultProvider
creates namespace/UUID.md files with readable titles and structured JSON records,
compatible with a local Obsidian vault. File projection/roundtrip is tested; no
Obsidian application, plugin or cloud synchronization was connected.

NotionProviderStub intentionally raises an unconfigured error. A future provider
must implement the same write contract, secure credential handling, least-privilege
access, remote conflict/version handling and actual authorized integration tests.
No external Notion API synchronization is implemented or claimed.

## Incremental synchronization and recovery

Queue identity is provider + record UUID + revision. Duplicate enqueues are idempotent.
Newer local revisions supersede queued older revisions. Remote hashes detect edits;
Markdown human edits/removals yield CONFLICT and are never silently overwritten.
Transient provider failures remain RETRY with exponential 2..300-second backoff;
five failed attempts become FAILED. Explicit retry records a diagnosis and keeps
remote conflict hashes. The queue persists offline and after restart. There is no
background scheduler: run sync explicitly or later configure an authorized worker.

Export/import retains stable IDs. Reimporting identical records is idempotent and
conflicting content needs explicit reconciliation; imports are transactional. Task
records imported from a different database instance retain origin task/instance
provenance without attaching themselves to an unrelated local task ID. A Markdown
import also passes the same validation/ACL/conflict checks. Do not import arbitrary
notes as trusted instructions or automatic factual authority.

Backup uses SQLite's consistent backup API and refuses an existing destination.
Restore validates integrity and writes to a new destination. See MIGRATION-V03.md.
Operational databases, vaults, exports and sync state are excluded from releases/Git.

## Explicit conflict resolution

Inspect a conflicted Markdown file and its current SHA-256 before deciding which
content to retain. To keep a remote edit, first review it and update the local
record through put with the current expected_revision. To retain the reviewed
local record, call `memory resolve --queue-id ID --expected-remote-hash HASH
--resolution "Actual inspected keep-local decision" --actor ACTOR --directory PATH`.
The operation rechecks the observed remote hash, records the resolution and queues
the local projection. Use MISSING only for an inspected missing file. A stale hash
is refused, and ordinary retry never acknowledges an external overwrite.
