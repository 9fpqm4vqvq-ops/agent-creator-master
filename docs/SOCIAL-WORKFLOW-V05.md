# Social Media & Digital Presence workflow

Social Media is general-purpose and independent of Income Shorts. Support businesses,
organizations, personal brands, launches, education, communities and supported platforms.
Never invent private competitor data, current trends, analytics, language verification,
rights or promotional claims. Drafts in English, Arabic or Sorani require appropriate
linguistic review. Copyrighted designs/media are references, not free-to-copy assets.

1. Create `projects create` with kind social, title, brief, measurable criteria and
   constraints. Management confirms objectives, audience, brand, sources and minimal team.
2. Route/assign through the existing workflow. Actually invoke the required researchers,
   writer/design/production specialists in the authenticated runtime. Read selected
   skills, recall current evidence, preflight and start within configured budgets.
3. Research dated platform/trend/audience evidence. Use authorized account data or
   label public observations and assumptions. Preserve historical sources in Vault.
4. Record strategy, content pillars, brand, milestones, costs and risks in the campaign.
   Create scoped child tasks for Web landing pages or Income Shorts services via Management.
5. Create content with `social create` after its assigned Social task is IN_PROGRESS:

```json
{
  "project_id":"CAMPAIGN_UUID","task_id":1,"platform":"instagram",
  "title":"Actual original draft","payload":{"copy":"Actual draft text","assets":[],"sources":[]},
  "scheduled_at":"2026-11-10T18:00:00+03:00","timezone":"Asia/Baghdad","timing_basis":"HYPOTHESIS"
}
```

The example date is illustrative. Replace every placeholder with actual project data.
Supported platform labels: instagram, facebook, tiktok, youtube, linkedin, x, pinterest,
other. Unknown platform support remains unconfigured, not inferred from these labels.
Timezones use the standard IANA database; proposed times are HYPOTHESIS unless an actual
analytics_reference supports ACCOUNT_ANALYTICS. A planned time does not schedule a post.

6. `social graphic` takes identity and writes an escaped local SVG draft. Add its path
   to the payload through update if it is part of the actual content; doing so invalidates
   prior review. Other supported tools can create assets only with actual access and cost
   authority. A video storyboard/HTML file is not a rendered video.
7. `social internal_review` takes identity and actual evidence. This moves DRAFT to
   REVIEWED, not APPROVED. Content/license/brand/accessibility corrections use update
   with identity, payload and expected_revision, returning it to DRAFT.
8. Submit real artifacts and complete independent QA, including specialized Social checks.
   The department result lists approved_content_ids and exact content_hashes. After the
   separately invoked QA PASS, `social approve` links identity and qa_task_id. Altered
   copy, assets, timing or timezone requires renewed review; snapshots retain all revisions.
9. `social export` takes project_id and writes actual CSV/Markdown calendar versions.
   States DRAFT, REVIEWED and APPROVED remain local. SCHEDULED/PUBLISHED require an
   actual verified external result; neither calendar export nor QA posts anything.
10. For publication/scheduling create a separate started Social action task with --project,
    inspect a tested runtime connector and use social publication_payload. Exact scoped
    approval binds that payload, subject hash, account/destination, operation and cost.
    `SocialService.publish` calls the configured adapter; schedule=true requires a future
    timestamp. SIMULATED adapters never change content into a live SCHEDULED/PUBLISHED state.
    Unknown external outcomes block blind replay and editing until read reconciliation.
11. Failed/unapplied operations retain receipts/history and need correction/new authority.
    Archived metadata does not delete a remote post. A real scheduled post must be cancelled
    through a separately authorized supported operation before archiving its local item.
12. Record actual analytics, reviewed lessons and final report through Master.

## Analytics and useful local fallbacks

`social analytics` accepts project_id, platform, rows, source, collected_at and
classification SUPPLIED_DATA (default), ESTIMATE or SIMULATED. It cannot label manual
rows CONNECTED. Rows may include impressions, reach, likes, comments, shares, saves and
clicks; missing values stay unknown. Count totals are sums of available values, not
claims of complete coverage. Engagement per impression is
(likes+comments+shares+saves)/impressions only when every row supplies all required fields.
Summed reach is not deduplicated audience reach. Retain actual dataset provenance.

Without a connector, produce original drafts, local assets, storyboards, production
briefs, calendars and sourced recommendations. Do not send replies, moderate accounts,
buy ads or publish merely because a source skill mentions doing so. Community output
is draft-only until actual scoped user authority and tool permissions are present.
