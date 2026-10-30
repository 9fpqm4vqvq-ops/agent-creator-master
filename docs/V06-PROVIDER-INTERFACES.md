# v0.6 model provider interfaces

Interface audit: **2026-10-30**. This document describes the implemented adapter
boundary, independently of orchestration and deployment readiness. An authenticated
CLI status, a configured API key reference, and passing simulated tests do not
establish successful model inference or independent model QA.

## Configuration and result contract

No provider is selected automatically. Missing/disabled configuration returns
`UnconfiguredAdapter`; invocation fails with the exact message
`EXECUTION UNAVAILABLE — MODEL RUNTIME NOT CONFIGURED`.

Explicit examples (choose one; these do not run or authenticate anything):

```json
{"enabled": true, "provider": "claude-code", "cli_path": "claude"}
{"enabled": true, "provider": "codex-cli", "cli_path": "codex"}
{"enabled": true, "provider": "openai-responses", "model": "YOUR_VERIFIED_MODEL", "api_key_env": "OPENAI_API_KEY"}
```

CLI model selection is inherited unless explicitly configured. The API requires a
model and its own credential; this interactive application does not supply a
programmatic model API or subscription entitlement to the project. Production
configuration cannot enable an injected HTTP transport or `SIMULATED` evidence.

`InvocationRequest` contains invocation/run/task IDs, agent, stage, refreshed
system/user prompts, an output object schema, workspace and timeout. `probe()`
returns public availability/authentication metadata without credentials.
`invoke(request, on_event, cancel_check, tool_gateway)` returns `InvocationResult`
with validated object data, provider, actual reported model when available,
invocation ID, provider reference, usage, duration, evidence kind and bounded tool
metadata. Codex JSONL does not establish its served model; that result is `null`,
even if a requested model was configured.

Errors distinguish missing runtime (`RuntimeUnavailable`), malformed or failed
provider execution (`ModelProtocolError`), cancellation (`ExecutionCancelled`) and
timeout (`ExecutionTimeout`). Public error callbacks include a bounded/redacted
code and message. Raw stdout/stderr are never written to the project database or
callback stream. Filesystem stdout/stderr capture by an external caller is outside
this module's control.

## Claude Code

The adapter starts a fresh headless invocation, using:

```text
claude --print --output-format stream-json --verbose
  --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}'
  --setting-sources= --permission-mode dontAsk
  --system-prompt PROMPT --json-schema SCHEMA --max-turns 1
```

User input goes to stdin. `--model` and `--max-budget-usd` are added only when
configured. No permission-bypass flag is used. The schema response is returned to
the controller for guarded artifact writing. **`--allowedTools` is an
auto-approval list, not a restriction on which tools exist.** Empty `--tools`
disables built-in tools; strict empty MCP configuration avoids inheriting account
or project MCP tools. These flags must be supported by the installed CLI. Settings
and MCP isolation do not constitute an operating-system sandbox. CLI/plugin
behavior and platform-managed policy still require deployment verification.

Readiness uses only `claude --version` and `claude auth status`. Public status
parsing is conservative. An unsupported/unknown auth response fails closed rather
than guessing. No Claude binary was available in the audit environment; no live
Claude success is claimed by the adapter tests.

Events consumed: system/init `session_id`; assistant `message.model`; result
`subtype`, `is_error`, `structured_output`/`result`, `usage`, `total_cost_usd`.
Only successful terminal results are accepted. `aborted_streaming` and
`aborted_tools` are failures. Thinking/redacted-thinking blocks and signatures are
discarded before callbacks. The parser does not persist full assistant messages.

The official SDK supports streaming interruption, session resume and fork; this
subprocess adapter deliberately uses none of those session reuse features. Fresh
sessions keep worker and QA contexts separate and avoid attributing cumulative
session usage to a single resumed invocation. Reported `total_cost_usd` is a
provider-reported cost figure, not independent evidence of an invoice or settlement.

## Codex CLI

The adapter uses the installed executable and fresh session:

```text
codex exec --json --sandbox read-only --cd WORKSPACE --ephemeral
  --skip-git-repo-check --output-schema TEMP_SCHEMA
  -c 'web_search="disabled"' -
```

The prompt goes to stdin and includes the refreshed controller instructions,
role/stage/task and artifact-only contract. An optional configured `--model` is
supported. The temporary schema contains no credential and is removed afterward.
The controller writes returned artifact JSON through its guarded engine.

The default preserves inherited user configuration and approval rules:
`--ignore-user-config`, `--ignore-rules`, unrestricted sandbox modes and dangerous
approval-bypass options are not added. A read-only filesystem sandbox restricts
filesystem writes; **it does not prove authenticated MCP/account tools are disabled**.
Native CLI tools do not pass through the injected Python `tool_gateway`. A prompt
instruction and tool metadata observation are not an external-action approval
barrier. Deploy this adapter only with separately verified host account-tool,
network and approval restrictions for its intended workload. Do not grant it
external write access merely because its filesystem sandbox says read-only.

Readiness uses `codex --version` and `codex login status`. The audited local binary
reported `codex-cli 0.163.0` and authenticated ChatGPT status. This establishes
CLI credential readiness, not successful generation or API access. Official
`codex doctor --json` is a non-generating diagnostic, but its full output can contain
environment details and should not be persisted indiscriminately. Managed
configuration supports `sqlite_home` and `log_dir` under applicable host policy;
the adapter does not relocate credential/state directories or override managed
requirements to make a run work.

Accepted JSONL events:

| Event | Adapter behavior |
| --- | --- |
| `thread.started` | Report public `thread_id` reference |
| `item.completed` + `agent_message` | Parse the final `text` as the schema object |
| `item.*` + `reasoning` | Drop completely |
| `item.*` + native tool | Report type/ID/status/exit-code metadata only |
| `turn.completed` | Require terminal success; map usage |
| `error`, `turn.failed` | Fail with a bounded, redacted public error callback |
| Nonzero process exit | Fail with a bounded matching stderr diagnostic; no raw transcript |

Codex usage is `input_tokens`, `output_tokens`, `cached_input_tokens`, and (when
reported) `cache_write_input_tokens`. No billed-dollar amount is inferred. Upstream
JSONL usage derives from cumulative thread totals, including on resume. The adapter
never resumes and does not sum resumed totals. The official CLI supports
`exec resume`, but a session reference in our result is not an automatic promise
that an ephemeral thread can later be resumed.

## OpenAI Responses API

Only the official HTTPS endpoint `https://api.openai.com/v1/responses` is accepted.
Credentials come from the configured environment variable at call time and are
sent as a Bearer header. Redirects and arbitrary alternative endpoints are refused.
Probe checks configuration presence without a billable request; `authenticated`
is unknown until an actual request succeeds. No credential value is reported.

Requests use `instructions`, user `input`, configured `model`, bounded
`max_output_tokens`, `store: false`, `parallel_tool_calls: false`, and strict
`text.format` JSON schema. Output text is collected from message/content
`output_text` entries across the output list. The adapter requires response
`status: completed`, a response ID and a schema-valid object. A `refusal`, incomplete
response or absent structured result cannot become a successful task artifact.
Transient reasoning items may be retained in memory only while continuing a tool
exchange; they are never emitted or returned as persisted evidence.

With no injected gateway, the adapter supplies no tools. An injected gateway may
provide `schemas()` (or `definitions()`) containing only explicitly declared
`type: function` definitions and `execute(name, arguments)`. Returned call names
must belong to that set, arguments must parse as JSON objects and satisfy the
declared schema, and every execution passes through the gateway. The gateway owns
approval, authorization, idempotency, secret access, budgets and tool execution.
Tool results are filtered/redacted before continuation. The function-call loop is
bounded (default four rounds), repeats the current instructions on every request,
and returns `function_call_output` for each `call_id`. Hosted browsing/computer/MCP
tools are not exposed by this adapter. An authorized function request is not proof
of a successful external side effect; use gateway receipts and reconciliation.

Response usage maps input/output tokens and
`input_tokens_details.cached_tokens`/`cache_write_tokens` when present. Each HTTP
response's usage is aggregated once. Missing counters remain unknown. API responses
do not establish billed USD; the adapter never manufactures an actual cost.

## Resource limits, cancellation and evidence

CLI invocation output is bounded (default 4 MiB total stdout/stderr), stdin is
written without shell interpolation, subprocesses use a new POSIX process group,
and cancellation/timeout terminates the owned group with TERM then KILL. This also
handles a child that outlives its process leader. Non-POSIX termination cannot
promise equivalent descendant containment. No resume occurs after termination.

HTTP requests use the remaining invocation timeout and bounded response reads.
Cancellation is checked before/after the blocking HTTP call and before each tool
execution; it cannot instantly interrupt that blocking call. Closing an HTTP
connection or killing a CLI cannot prove that the remote computation or action
stopped, or that no charge occurred. OpenAI's documented cancellation endpoint is
for background responses; this adapter does not create background requests and
does not claim remote cancellation. Reconcile uncertain external work before retry.

Usage records have input/output/cache counters, `token_kind`, `actual_cost` and
`estimated_cost`; missing values stay `null`/`UNKNOWN`. Configuring a monetary
budget does not make unknown billing measured. CLI accounting may expose totals
only at completion, so controller preflight budgets remain necessary.

All adapter unit fixtures are explicitly `SIMULATED`, using local fake executables
or injected HTTP transport. They verify parsing, safe arguments, cancellation,
process-group cleanup, schema rejection and gateway boundaries, not production
credentials or live model quality. Real acceptance must separately record actual
provider references, sanitized diagnostics and usage. The first bounded local
Codex smoke failed before any provider event; it is not evidence of live completion.

## Authoritative source snapshots

These interfaces were checked against official repositories, not third-party
wrappers. Recheck installed CLI compatibility when upgrading.

| Source | Pinned official source |
| --- | --- |
| Codex JSONL event schema | [exec_events.rs](https://github.com/openai/codex/blob/f752c97f7d0be0cbef5cece327f52a16ad6fb1c6/codex-rs/exec/src/exec_events.rs) |
| Codex JSONL usage generation | [event_processor_with_jsonl_output.rs](https://github.com/openai/codex/blob/f752c97f7d0be0cbef5cece327f52a16ad6fb1c6/codex-rs/exec/src/event_processor_with_jsonl_output.rs) |
| Codex subprocess/abort contract | [SDK exec.ts](https://github.com/openai/codex/blob/f752c97f7d0be0cbef5cece327f52a16ad6fb1c6/sdk/typescript/src/exec.ts) |
| Codex config including state paths | [config_toml.rs](https://github.com/openai/codex/blob/f752c97f7d0be0cbef5cece327f52a16ad6fb1c6/codex-rs/config/src/config_toml.rs) |
| Codex headless documentation | [Official non-interactive guide](https://developers.openai.com/codex/noninteractive) |
| Claude tool availability versus approval | [Official SDK README](https://github.com/anthropics/claude-agent-sdk-python/blob/1ea8cb74ddcdadbfaa9b20dfa8268e18047851e7/README.md) |
| Claude result/session/usage types | [types.py](https://github.com/anthropics/claude-agent-sdk-python/blob/1ea8cb74ddcdadbfaa9b20dfa8268e18047851e7/src/claude_agent_sdk/types.py) |
| Claude supported CLI transport flags | [subprocess_cli.py](https://github.com/anthropics/claude-agent-sdk-python/blob/1ea8cb74ddcdadbfaa9b20dfa8268e18047851e7/src/claude_agent_sdk/_internal/transport/subprocess_cli.py) |
| Responses request and cancellation methods | [responses.py](https://github.com/openai/openai-python/blob/05992039b9f7b78a48cf1e5a35727ba27d96db6e/src/openai/resources/responses/responses.py) |
| Responses usage fields | [response_usage.py](https://github.com/openai/openai-python/blob/05992039b9f7b78a48cf1e5a35727ba27d96db6e/src/openai/types/responses/response_usage.py) |
| Responses function schema | [function_tool_param.py](https://github.com/openai/openai-python/blob/05992039b9f7b78a48cf1e5a35727ba27d96db6e/src/openai/types/responses/function_tool_param.py) |

The pinned upstream snapshots can contain features newer than an installed CLI.
Version output and successful end-to-end acceptance with that installed binary
remain required; unsupported flags should fail visibly rather than be silently
removed or replaced with weaker controls.

## v0.6 orchestration enforcement

Before Codex inference the adapter calls the supported `codex mcp list --json`
discovery command and rejects enabled servers or unverifiable output. The caller
must use an appropriately restricted host profile; read-only filesystem sandboxing
is not a guarantee against reading all host files. No auth/config guards are bypassed.
