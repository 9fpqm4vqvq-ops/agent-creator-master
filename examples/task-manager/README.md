# Task desk: reviewed local acceptance fixture

This is human/controller-authored validation source, not a live model-generated or
QA-approved acceptance result. No deployment. Open index.html through a local static
server. Supports add, completion, all/active/completed filtering and localStorage.
No external network dependencies; malicious title text is rendered as text.

`node test-app.js` performs real JavaScript state/persistence/input/error tests and
explicit DOM-fixture integration. Responsive/accessibility/browser assertions
require `browser-test.html` in a real sandboxed browser. Never call DOM fixtures a
browser test. No browser sandbox-disabling flag is authorized.

To use in isolated runtime acceptance, copy reviewed source into a run workspace,
pin verifier hashes in operator-owned acceptance.verifier_files, authorize exact
argv checks, and use a reviewed Node/browser image. A deliberate initial defect
in `visible('completed')` must fail functionality; restore the reviewed code and
rerun. That local correction demonstration is distinct from actual model QA.
