# v0.7 connector evidence inventory

October 30, 2026. Availability is scoped to the observed host, not automatically
inherited by the downloadable Claude Code project. No provider endpoints invented.

| Capability | Observed status | Evidence / missing prerequisite |
|---|---|---|
| GitHub host connector | LIVE TESTED READ | Actual repository access, README content, commit list, PR list and issue list returned successfully; sanitized receipts in validation-v07/github-reads.json |
| GitHub branch/PR write | Explicitly authorized release workflow only | Dedicated v0.7 branch and review PR; main and previous archives preserved. Not permission for arbitrary repository writes |
| Downloaded GitHub REST adapter | IMPLEMENTED / UNCONFIGURED here | GET repository/contents/commits/issues/PRs/search; requires permitted REST networking and appropriate token for private/authenticated operations |
| Figma | AVAILABLE CATALOGUE / NOT CONNECTED | Official connector found, not installed/connected at inspection; no file access, editing or asset capability tested |
| Higgsfield | AVAILABLE CATALOGUE / NOT CONNECTED | Official account plugin found, not installed/connected at inspection; no generation, account permission, price or credit usage verified |
| HyperFrames | SOURCE REFERENCE ONLY / UNVERIFIED RENDERER | Reviewed upstream manifest/README describe CLI/SDK and MP4 rendering. Full executable/build dependencies are not bundled; source description is not a rendered video or hosted API |
| Native image generation | HOST TOOL AVAILABLE / NOT LIVE TESTED | Current host exposes image generation; no test requested an actual brand image, no price/rights assumption, no unattended project binding |
| General web search | BLOCKED HOST ATTEMPT / INTERFACE IMPLEMENTED | Search tool returned isError with no result records; no successful search claimed; explicit NativeWebSearchAdapter contract retained |
| Social analytics/publishing | UNCONFIGURED | No connected account scopes or actual API receipts. Draft creation stays local. Analytics needs genuine datasets. Publishing/scheduling/messages/ads retain separate scoped approval |
| Notion/Drive/deployment | UNCONFIGURED | Existing capability discovery and authorization retained; no new read/write success claimed |

Figma and Higgsfield require installation/connection and account authorization
before relevant operations can be checked. No unconfirmed connection is used.
Connector discovery descriptions do not prove permissions or write support. Existing
write intent, exact subject/argument/cost scope, receipt verification and ambiguous
outcome reconciliation controls remain unchanged. The new operational_status view
never promotes SIMULATED connector tests to live tested capabilities.
