# Web & Application Development workflow

First inspect an existing repository and real requirements. Reuse working technology;
do not recommend a rewrite or a single default framework. The department supports
websites, applications, APIs, database-backed systems, PWAs and maintenance; mobile
implementation/builds are conditional on actual SDKs. Research official versions,
security advisories and compatibility with dates. Unverified claims stay UNVERIFIED.

1. Create a software project with `projects create --data work/project.json`:
   `{"title":"Example project","brief":"Actual requirements","criteria":"Measurable actual acceptance criteria","kind":"web","constraints":["Actual constraints"]}`.
2. Use the returned task_id with management-review, plan and assign. Select
   master-workflow, web-project-workflow and the smallest appropriate registered
   specialist skills. Identify complexity and rationale. For child work, use
   projects decompose after parent Management review. Scope by need, not every role.
3. Dispatch, read selected instructions, recall project/department evidence, record
   current preflight, then start with a real invocation reference and projected cost.
   Actually invoke the worker in the authenticated runtime; the CLI does not do this.
4. Record requirements, source-linked technology decisions, design system, architecture,
   risks and milestones with projects update. It accepts identity, changes and
   expected_revision. Verified technology decisions require dated VERIFIED sources.
   An operator label still is not evidence that a URL was visited.
5. Implement actual software. Optional local helper:
   `projects scaffold` data `{"identity":"PROJECT_UUID","task_id":1,"template":"static-site"}`
   or template python-api. Helpers create files and run instructions, do not deploy.
   Other technology choices are actual engineering tasks in the runtime. The generated
   API defaults to loopback port 8081, with WEB_PROJECT_PORT as an explicit test override.
6. Execute suitable unit/integration/browser/keyboard/responsive/accessibility tests,
   review security/dependencies/performance and record actual results. Resolve defects.
7. Submit actual artifacts, authors, sources/limitations and specialized QA evidence.
   For project approval include `approved_project_ids:[UUID]` and
   `project_record_hashes:{UUID:CURRENT_RECORD_HASH}` in the department result.
   Obtain a separate independent qa-auditor invocation and use the existing review
   command. REWORK returns precise failures to the assigned owner.
8. `projects approve` takes identity and qa_task_id of the completed exact-byte review.
   Edits or altered outputs invalidate the binding. Record lessons through Vault.
9. A deployment needs a separately scoped, started Web task referencing --project UUID,
   a current tested connector with explicit deploy permission, exact payload from
   projects deployment_payload, actual cost forecast and exact scoped user authority.
   `ProjectService.deploy` calls the configured adapter and retains its verified receipt.
   A simulated receipt stays SIMULATED. A plan/ready flag never means deployed.
10. Return approved outcomes through Master. Preserve setup, build, rollback and known
    limitations. Use the existing maintenance/update pipeline for future changes.

## Scoped collaboration example

Data for projects decompose:

```json
{
  "identity":"PROJECT_UUID",
  "scopes":[
    {"name":"page","department":"web-development","agent":"web-frontend-engineer","request":"Build the specified page","criteria":"Actual usable files and tests"},
    {"name":"launch","department":"social-media","request":"Prepare original launch copy","criteria":"Source-backed reviewed content","depends_on":["page"]}
  ]
}
```

Each child still needs Management planning/assignment, current preflight/start and
independent QA. The parent cannot complete with unfinished or broken child deliverables.
Iraq E-commerce may own commercial feasibility; Web owns software and Social owns
campaign strategy. Exchange documented artifacts/handoffs, not unrestricted memory access.
