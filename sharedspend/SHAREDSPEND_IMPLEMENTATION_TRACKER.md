# SharedSpend — Implementation Tracker & Roadmap

> **Purpose:** This is the working implementation tracker for SharedSpend.
> Update this file after each feature is implemented and validated so the next
> implementation is always clear.
>
> **Source:** Based on the existing `# SharedSpend — Implementation Plan.txt`,
> the existing `sharedspend-handoff.docx`, and the implementation decisions
> already made during development. Current status entries reflect the actual
> progress known as of September 23, 2026.

---

## 1. How to Use This File

Status values:

- `[x]` **DONE** — implemented and validated.
- `[~]` **IN PROGRESS** — currently being implemented.
- `[ ]` **PENDING** — agreed, but not started.
- `[!]` **BLOCKED / NEEDS DECISION** — requires a decision or dependency.

For every completed feature, record:

1. Implementation commit
2. Backend tests
3. Frontend tests/build
4. Manual verification, where applicable
5. Any known follow-up/caveat

### Development workflow

```text
SharedSpend-clone
    ↓
Implement one feature
    ↓
Backend tests / frontend tests / build
    ↓
Manual verification
    ↓
Review git diff
    ↓
Commit + push SharedSpend-clone
    ↓
Promote tested work to private SharedSpend master
```

**Repository rule:** `SharedSpend-clone` is the development repository. The
private `SharedSpend` repository is the stable/master repository.

---

# 2. Current Project Status

## Environment / baseline

- [x] Fresh `SharedSpend-clone` checkout on personal laptop
- [x] Python 3.11.9 environment created
- [x] Backend dependencies installed
- [x] Backend tests pass: **66/66**
- [x] Node.js v24.21.0 available
- [x] npm 11.19.0 available
- [x] Frontend dependencies installed
- [x] Frontend production build passes
- [ ] Frontend test suite run on personal laptop
- [ ] Final Phase 2 regression suite
- [ ] Production-readiness review

Current development baseline:

```text
Branch: main
Known baseline commit:
506511b feat: add spending forecast to analytics and dashboard
Working tree: clean at the time of baseline verification
```

---

# 3. Phase 1 — MVP

The original implementation plan defines the MVP as a shared budget and personal
expense tracker with authentication, groups, budgets, transactions,
rule-based categorization, dashboard, analytics, and basic tests.

## MVP feature checklist

- [x] User registration/login
- [x] Group creation/joining
- [x] Monthly shared budget
- [x] Shared transactions
- [x] Personal transactions
- [x] Rule-based categorization
- [x] Global/group categories
- [x] Dashboard
- [x] Transaction filtering
- [x] Analytics
- [x] Insights
- [x] Member contribution display
- [x] Responsive UI
- [x] Backend test coverage established

### Original MVP exclusions now moved into later phases

- [x] Multiple groups → Phase 2
- [x] Settlement → Phase 2
- [x] AI categorization → Phase 2
- [x] Export → Phase 2
- [x] Notifications → Phase 2
- [x] Dark mode → Phase 2
- [x] E2E testing → Phase 2 / quality gate

---

# 4. Phase 2 — Product Expansion

## Phase 2 agreed implementation order

### 2.1 Multiple Groups / Group Switcher

**Status:** `[x] DONE`

Scope:
- Support multiple groups per user.
- Group switcher in the application shell.
- Active group controls group-scoped dashboard, transactions and analytics.

Validation:
- Implemented and tested.
- Group dropdown UI overlay issue fixed.
- Existing group functionality retained.

---

### 2.2 Settlement Calculation / Tracking

**Status:** `[x] DONE`

Scope:
- Calculate who owes whom from shared transactions.
- Record settlement actions.
- Track outstanding settlement amounts.
- Reflect settled amounts in the displayed outstanding balance.

Validation:
- Settlement calculation/update invalidation fixed.
- Settlement UI verified with partial/outstanding amounts.
- Transaction/settlement interaction tested.

Known caveat:
- Current period filtering of settlement records uses settlement `created_at`.
  Revisit this if historical-period settlement behavior becomes a requirement.

---

### 2.3 AI / LLM Categorization

**Status:** `[x] DONE / IMPLEMENTED`

Scope:
- Replace/extend rule-based categorization through the existing
  `CategorizerService` seam.
- Preserve user override.
- Keep existing categorization API compatibility.

Notes:
- The original implementation plan explicitly designed `CategorizerService`
  so an `LLMCategorizerService` could be introduced without changing the
  router/frontend contract.
- Confirm the exact provider/model and production credential strategy before
  making provider-specific changes.

---

### 2.4 AI Spending Insights

**Status:** `[x] DONE / CURRENT IMPLEMENTATION`

Scope:
- Spending insights for the selected group/period.
- Highest category.
- Highest-spend day.
- Largest transactions.
- Spending trend.
- Monthly spending forecast.

Current implementation includes:
- `/analytics/insights`
- `/analytics/forecast`
- Analytics-page forecast card
- Dashboard spending forecast card

Important clarification:
- The current forecast is **rule-based linear extrapolation**, not an ML model.
- The current `get_insights` implementation is rule-based analytics, not an LLM
  narrative engine.
- The original roadmap's AI narrative endpoint remains a possible future
  enhancement if a true LLM narrative is desired.

Forecast formula:

```text
projected_spend =
    shared_spent / days_elapsed * days_in_month
```

---

### 2.5 CSV Export

**Status:** `[~] IN PROGRESS — implementation and automated checks pass; browser download verification pending`

Planned scope:
- Export filtered transactions as CSV.
- Respect the same filters used by the transaction list:
  - group
  - type
  - category
  - payer
  - date/date range
  - month/year
- Export should use real backend data.
- Preserve decimal amounts and dates consistently.
- Provide a clear frontend download action.

Original architecture direction:
- `GET /transactions/export`

Acceptance criteria:
- [x] Backend export endpoint implemented
- [x] Same authorization rules as transaction listing — implementation shares the list query
- [x] Filters match transaction-list behavior — implementation shares the list query
- [x] CSV headers defined
- [x] Frontend download action — tested with the selected filters
- [x] Backend tests — filtered export, authorization, empty output, headers, date and decimal amounts
- [x] Frontend tests — request filters and download behavior
- [x] Production build — passed
- [ ] Manual download verification

Validation note (2026-09-24): The full backend suite passed (84/84), the frontend
suite passed (83/83), the production build passed, and `git diff --check` passed.
The export endpoint returned CSV in the browser smoke test, but the browser
download event could not be captured; final manual download verification remains
pending, so this feature remains IN PROGRESS.

---

### 2.6 Budget Copy / Carry Forward

**Status:** `[~] IN PROGRESS — implementation and automated checks pass; manual UI verification pending`

Planned scope:
- Carry the previous month's budget into the next month.
- Allow the user to review/edit before saving.

Original architecture direction:
- Budget endpoint with a copy-from-previous-month capability.

Acceptance criteria:
- [x] Backend API returns the previous calendar month's amount without writing it
- [x] Frontend action fills the editable amount; the user must save explicitly
- [x] Existing current-period budgets are updated through the existing upsert, not duplicated
- [x] API and cross-screen integration tests
- [x] Build
- [ ] Manual verification

Validation note (2026-09-24): Backend tests passed (84/84), frontend tests passed
(83/83), production build passed, and `git diff --check` passed. The isolated
browser smoke verified account registration, group creation, and matching
Dashboard/Forecast budget and spend values. Manual previous-month copy remains
pending.

---

### 2.7 Budget Threshold Notifications

**Status:** `[~] IN PROGRESS — in-app/browser alerts implemented; background delivery remains undecided`

Planned scope:
- Alert when shared spending reaches configured budget thresholds.
- Browser notifications and in-app alerts while SharedSpend is open.
- Default thresholds are 80% and 100%; the user opts in from Settings.
- Avoid duplicate notifications.
- Weekly/monthly summaries are not implemented.

Dependencies/decisions:
- [ ] Choose a provider for email/background push delivery
- [x] Define threshold values (80% and 100%)
- [x] Define opt-in preference and per-user/group/month duplicate suppression
- [ ] Configure credentials and background-job delivery if email/push is required

Known limitation: Alerts appear only while the app is open. The preference and
deduplication state are stored on the current browser/device, not in the shared
database. This does not provide cross-device or background delivery.

This should be implemented after core budget functionality is stable.

---

### 2.8 Dark Mode

**Status:** `[~] IN PROGRESS — toggle and persisted theme pass automated checks; visual review pending`

Planned scope:
- Theme toggle.
- Persist user preference.
- Apply dark theme consistently across existing components.
- Check charts, dropdowns, forms and dialogs.

Acceptance criteria:
- [x] Theme toggle
- [x] Persisted device preference
- [ ] Dashboard verified visually
- [ ] Transactions verified visually
- [ ] Analytics/charts verified visually
- [ ] Settings verified visually
- [ ] Mobile verified
- [x] Build/tests pass

---

### 2.9 E2E / Phase 2 Quality Gate

**Status:** `[~] IN PROGRESS — cross-screen API integration scenario passes; browser E2E/manual review pending`

Although E2E was originally listed separately from the Phase 2 feature list,
it should be treated as a Phase 2 quality gate before declaring Phase 2
complete.

Planned critical flows:
- [x] Register/login and two-user group membership through real API routes
- [x] Create/join groups and verify group-scoped queries
- [x] Set budget and verify Dashboard/Analytics/Forecast responses
- [x] Add shared and personal transactions; verify date/search/payer filters
- [x] Analytics, forecast, CSV filtering, privacy, and empty results
- [x] Settlement in both directions, source/history linkage, and debtor payment visibility
- [x] Admin authorization and migration/schema tests
- [x] XLSX bytes parse as a real workbook in the frontend test
- [x] Budget copy API and dark-mode preference tests
- [ ] Browser-driven E2E and manual visual/download verification

---

# 5. Phase 2 Completion Gate

Phase 2 should not be marked complete until:

- [ ] All agreed Phase 2 features implemented
- [ ] Backend tests pass
- [ ] Frontend tests pass
- [ ] Frontend production build passes
- [ ] Critical E2E/user flows verified
- [ ] No known blocker bugs
- [ ] No accidental debug/mock code
- [ ] Git working tree reviewed
- [ ] Documentation updated
- [ ] User-approved release/promotion step (outside this development-only review; do not modify the private repository)

Regression validation note (2026-09-24): The real API integration scenario covers
two authenticated users and two groups across budget, transactions, analytics,
forecast, privacy, CSV, settlement and source/payment linkage. An isolated
browser smoke covered registration, group creation, budget save, transaction
creation, and Dashboard/Forecast consistency. It caught a conditional-hook bug
in the new alert effect; that bug was fixed and covered by a Dashboard render
transition test. Full backend and frontend automated suites and the production
build pass. Phase 2 remains open for manual export/copy/theme review and a
decision on background notification delivery. No live PostgreSQL/Neon instance
was available for integration tests.

Environment caveat: the pre-existing services on `localhost:5173` and
`localhost:8000` were already running and displayed a budget discrepancy
(Settings and Forecast showed the saved budget while Dashboard showed “Not
set”). Those services were not started from this test run, so their code and
database could not be validated safely. The current checkout, running against
an isolated temporary SQLite database, showed consistent Dashboard and Forecast
budget/spend values. A temporary test account (`review_ale`), group
(`Review Household`), and ₹1,000 budget were created in the pre-existing local
app during the initial port-collision attempt; the test account was signed out
and those rows were left untouched.

**Next implementation after this baseline:** CSV Export.

---

# 6. Phase 3 — Advanced Intelligence & Automation

Phase 3 remains intentionally separate from the current Phase 2 completion work.

## 3.1 Natural-Language Transaction Entry

**Status:** `[ ] PENDING`

Example:

```text
"paid 160 for vegetables today"
```

Expected behavior:
- Parse amount
- Parse description
- Infer date
- Suggest category
- Suggest transaction type where appropriate
- Pre-fill transaction form
- User confirms before saving

Important:
- Natural-language parsing should not silently create transactions without
  confirmation unless explicitly designed later.

---

## 3.2 Recurring Transactions

**Status:** `[ ] PENDING`

Scope:
- Daily/weekly/monthly/custom recurrence
- Start date
- Optional end date
- Pause/resume
- Automatic transaction generation
- Duplicate prevention
- Auditability

Likely needs:
- New recurrence model
- Scheduler/background mechanism
- User controls
- Notification/error handling

---

## 3.3 Anomaly Detection

**Status:** `[ ] PENDING`

Scope:
- Identify unusually large or unusual spending.
- Consider category, historical behavior and frequency.
- Explain why a transaction was flagged.
- Avoid excessive false positives.

Potential implementation:
- Start with statistical/rule-based detection.
- Later evolve toward ML if sufficient transaction history exists.

---

## 3.4 ML-Based Spending Forecast

**Status:** `[ ] PENDING`

Current Phase 2 forecast is linear extrapolation.

Phase 3 goal:
- Replace/improve linear extrapolation using historical spending patterns.
- Consider seasonality and category trends where sufficient data exists.
- Compare model output against the existing baseline.

Acceptance should include:
- [ ] Historical data preparation
- [ ] Baseline comparison
- [ ] Model evaluation
- [ ] Fallback when insufficient data
- [ ] API integration
- [ ] UI integration
- [ ] Tests

---

## 3.5 Mobile Application

**Status:** `[ ] PENDING`

Planned technology:
- React Native
- Existing FastAPI backend reused

Scope:
- Authentication
- Dashboard
- Transactions
- Groups
- Analytics
- Settlement
- Notifications
- Mobile-specific UX

---

## 3.6 Offline Support

**Status:** `[ ] PENDING`

Potential architecture:
- Service worker / offline-capable frontend
- Local transaction queue
- Sync mechanism
- Conflict handling
- Retry handling

This should be designed after the web application's data contracts are stable.

---

## 3.7 Multi-Currency

**Status:** `[ ] PENDING`

Scope:
- Per-group currency
- Currency display
- Exchange-rate integration
- Historical exchange-rate handling where required
- Reporting rules when transactions use different currencies

The original MVP architecture already contains a group currency field, but
full multi-currency behavior is intentionally deferred.

---

# 7. Phase 4+ — Future / Not Yet Locked

These are **not yet an agreed implementation commitment**. Keep them here so
they are visible without accidentally treating them as current requirements.

## Potential Phase 4 areas

- [ ] Advanced personalized spending recommendations
- [ ] Smarter budget recommendations
- [ ] Personalized category learning
- [ ] Advanced financial dashboards
- [ ] Household/member financial goals
- [ ] Savings goals
- [ ] Subscription detection
- [ ] Receipt/image-based transaction entry
- [ ] Bank/UPI integration
- [ ] Advanced notification center
- [ ] Shared financial reports
- [ ] Production cloud deployment
- [ ] PostgreSQL production migration
- [ ] CI/CD
- [ ] Observability and monitoring
- [ ] Backup/recovery automation

**These require explicit approval before implementation.**

---

# 8. Production Readiness Track

This track is independent of feature phases and should be revisited before
public/end-user release.

- [ ] Strong production `SECRET_KEY`
- [~] Shared PostgreSQL configuration, additive Alembic migration, global admin
  APIs and admin UI implemented; actual PostgreSQL/Neon integration still needs
  verification against a live database.
- [~] PostgreSQL migration generated in offline mode and SQLite migration
  executed successfully; live PostgreSQL migration remains unverified.
- [ ] Production CORS configuration
- [ ] HTTPS/TLS
- [ ] Database backup strategy
- [ ] Restore/recovery test
- [ ] Rate limiting review
- [ ] Authentication/security review
- [ ] Dependency vulnerability review
- [ ] CI/CD pipeline
- [ ] Error monitoring/logging
- [ ] Frontend deployment
- [ ] Backend deployment
- [ ] Production smoke test

---

# 9. Known Existing Project Documents

A previous implementation-plan document already exists:

`# SharedSpend — Implementation Plan.txt`

It contains the original architecture, MVP scope, Phase 2 list, Phase 3 list,
API design, testing strategy and future AI integration points.

A handoff document also exists:

`sharedspend-handoff.docx`

It contains the MVP status, known gaps, production checklist and future-phase
roadmap.

**This tracker does not replace those documents.** It is the day-to-day
implementation status layer. The original plan remains the architectural
reference; this file tracks what has actually been implemented.

---

# 10. Change Log

## 2026-09-23

- Created this implementation tracker.
- Confirmed existing implementation plan and handoff documents.
- Confirmed fresh personal-laptop backend environment.
- Confirmed backend tests: 66/66.
- Confirmed frontend dependencies installed.
- Confirmed frontend production build passes.
- Confirmed current development baseline includes spending forecast.
- Confirmed next planned implementation: **CSV Export**.
- Phase 2 features already completed: Multiple Groups, Settlement,
  AI/Categorization work, Analytics/Insights/Forecast work.

## 2026-09-24

- Added `asyncpg==0.31.0`, PostgreSQL `DATABASE_URL` support, Neon pooler
  connection handling, and an additive Alembic revision for admin and settlement
  schema fields.
- Added controlled global-admin promotion, protected user management and
  database migration-health APIs, and a simple admin UI.
- Backend tests passed: 77/77. Frontend tests passed: 73/73. Production build
  passed. `git diff --check` passed.
- SQLite Alembic upgrade passed; PostgreSQL offline Alembic SQL generation
  passed. No live PostgreSQL/Neon database was configured, so PostgreSQL
  integration is not verified and the foundation remains IN PROGRESS.
