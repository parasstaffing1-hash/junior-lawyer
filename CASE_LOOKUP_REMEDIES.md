# Case Lookup + Legal Remedy Analysis

Batch 29 adds two connected, deterministic-first workflows.

## Case Lookup

The Case Lookup service detects exact CNR input, typed case-number input such as `CS 234/2025`, bare number/year input, and free text. Saved lawyer state/district/court preferences influence ranking but never silently remove other valid candidates.

The application normalizes every supported source into the same `CaseRecordData` shape: court, case identifiers, parties, advocates, judge/bench, Acts/sections, status/stage, hearings, orders, judgments, source provenance and timestamps.

Current source boundary:

- saved/local cache works directly;
- normalized official imports work directly;
- district-court, High Court and Supreme Court adapters expose a user-assisted / approved-connector boundary;
- the application does **not** bypass CAPTCHA or imply a live refresh when the official source has not actually been checked.

Saving a case creates immutable source snapshots. A later refresh is compared deterministically and material changes (stage, hearing date, judge, parties, advocates, Acts, orders, judgments, etc.) are stored as structured changes.

## Legal Remedy Analysis

`Find Legal Remedies` is available inside the Case Workspace and on a saved case page. The analysis context includes the normalized case record, current stage/status, latest order/judgment, court, Acts/sections, hearing history, and linked matter documents.

The deterministic engine only evaluates **active, verified remedy rule packs**. An active pack is rejected at creation time unless:

1. the pack is marked verified;
2. every rule is verified; and
3. every rule has at least one verified legal authority.

A rule can match stage, status, court level, order type, Act and section; require an order/final outcome; evaluate maintainability checks; compute a deadline only from an explicit verified trigger/rule; check required-document availability; and expose procedural steps and risks.

If verified coverage is missing, Junior Lawyer produces research prompts/coverage warnings. It does **not** turn generic taxonomy such as “appeal/revision/review” into a maintainability conclusion.

### Limitation safety

The calculator never invents a trigger date. A rule with missing days/trigger data returns `needs_review`. Rule packs should also preserve the controlling source citation, exceptions/exclusions, condonation considerations and effective-date/version metadata. Lawyer review remains mandatory.

### Authorities and precedent

Candidates copy verified statute/rule/judgment authorities from the governing rule. Relevant case-law can therefore be attached to a rule from the local verified legal corpus. Unverified authorities are not promoted into the candidate's verified-authority list.

### Memo and drafting

A lawyer can generate a detailed deterministic memo in English, Hindi or bilingual form. The memo includes applicability reasons, forum, deadline status, maintainability checks, documents/evidence, procedural steps, risks and verified authorities.

A selected candidate can open the existing source-backed Legal Drafting engine for an appeal/petition/application/revision/review/writ/bail/stay/injunction/quashing/execution/restoration/recall workflow. The existing lawyer-review and source-provenance gates remain in force.

Complex remedy comparison, nuanced reasoning and bespoke drafting may be routed to the existing evidence-bounded AI layer. Remote AI still requires explicit permission and existing matter security policies apply.

## Examples

- `case_lookup_examples/official-case-record.example.json` is synthetic and contains no real case/legal authority.
- `remedy_examples/remedy-pack.template.json` is intentionally **draft + unverified**. It is a schema/template, not substantive Indian legal advice.
- `remedy_examples/remedy-taxonomy.json` is product taxonomy only.

## Release-candidate impact

Batch 28 RC evidence predates this feature. Batch 29 therefore changes the candidate version/database revision and adds a critical RC scenario for Case Lookup + Legal Remedy Analysis. Production/pilot RC validation must be rerun after verified remedy packs and approved official-source connector/user-assisted flows are configured.
