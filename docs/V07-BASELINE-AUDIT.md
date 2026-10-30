# v0.7 baseline audit and repair plan

Inspected default branch main, commit e1e94d17ed29c6de3514021098c742f9ea4c01c9.
Re-ran all existing suites before editing: 255 root + 15 MAOS + 12 Income + 5 Shorts
+ 315 Trading = 602 PASS. Required root contracts and v0.6 runtime/provider/QA/
reliability documentation reviewed. Preserve all 70 roles and 176 reviewed skills.

| Feature | Existing status | Planned change |
|---|---|---|
| CLI/API adapters | IMPLEMENTED, live inference UNVERIFIED | Unique live probe with receipts and exact prerequisites/errors |
| Management/specialist/QA | IMPLEMENTED, live acceptance BLOCKED | Preserve contexts; repair receipt/recovery gaps and add functional acceptance |
| Model receipt + telemetry | BROKEN failure boundary | Provider output is lost if telemetry validation fails; persist receipt separately |
| Corrective context | PARTIAL | Existing workspace lists hashes, not file contents; provide bounded actual contents |
| Web QA command proof | PARTIAL | Any PASS command, including /bin/true, currently counts; require assertion evidence bound to reviewed verifier bytes |
| QA test references | PARTIAL | A QA claim can cite a prior-byte check; require current-byte evidence |
| General search | MISSING provider binding | Supported trusted host search interface with explicit no-provider behavior |
| HTTP research through proxy | UNCONFIGURED/BLOCKED here | Preserve DNS security; support explicit native-host source validation without fake DNS |
| GitHub reads | PARTIAL | Add bounded documented commits/issues/PR reads; keep writes separately authorized |
| Figma/social/media | UNCONFIGURED or host-specific | Inventory actual interfaces, avoid operational claims without verified calls |
| Recovery | PARTIAL | Operator inspection, receipt reconciliation, safe checkpoint/replacement interface |
| Concurrency and run budgets | MISSING | Atomic shared capacity and run-level conservative budget gate |
| Dashboard | IMPLEMENTED, classifications PARTIAL | Explicit simulated/local/live/blocked/unverified evidence and held costs |
| Setup | PARTIAL | Replace mixed-version quick start with coherent v0.7 instructions |

No provider installation, credential extraction, sandbox weakening, default-branch
push, deployment or external publication is part of the acceptance work. Tests
must distinguish actual local behavior, live provider calls and simulated models.
