# Execution workspace boundaries

See RUNTIME-V06.md for operator configuration and actual-check authorization.
`WorkspaceManager` guards paths, traversal, symlinks, hardlinks, sensitive filenames,
private reasoning markers, per-file/total sizes and immutable artifact exports.
Writes require the previous content hash for existing files. These application
checks alone are not OS isolation.

`probe_isolation()` actually runs a fixed harmless command inside the selected
Docker/bubblewrap backend. No probe success means no generated code execution.
`approve_command()` binds an explicit operator reference, exact argv and input hash;
`run_check()` refuses changed inputs and records real exit code, bounded output,
timeout/cancellation and processes. Dependency installation remains unavailable in
the network-none executor. Operators supply reviewed images containing dependencies.

ToolGateway binds the actual persisted task, run, invocation and agent. QA is
read-only and cannot create command approvals. Subprocess environments omit model
credentials and preload variables. Docker targets the managed local socket while
clearing endpoint/TLS selectors, preserving host proxy/CA and Docker registry config.
No container receives the host Docker socket or provider credentials.

Actual validation: Docker probe and a fixed Python functional-check process passed.
Bubblewrap failed its actual probe. Deterministic isolation fixtures remain explicitly
simulated and do not certify a sandbox. See V06-ACCEPTANCE.md for evidence.

Unconfirmed container cleanup persists CLEANUP_REQUIRED and blocks further command
execution and instruction activation until reconciled. Cancellation callbacks are
bound by the host, including checks called through a model gateway.
