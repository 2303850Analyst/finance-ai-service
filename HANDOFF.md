# Continuation state - 2026-11-13, Mini App deployed

## Scope

The user explicitly requested completing this existing local MVP with Telegram voice input, confirmation and GenBI, deploying and testing it. Earlier Stage 2 prohibitions in AGENTS.md describe an old stage; the current request explicitly scheduled these integrations. Financial domain rules still apply.

## Implemented

- Telegram transport in backend/app/telegram_bot.py: separate Compose service, aiogram polling.
- Binding: single-use hashed expiring pairing tokens; bound private-chat owner; internal API secret; link/revoke UI.
- Drafts: separate PostgreSQL operation_drafts, 24-hour expiry, cancellation, row-locked idempotent atomic confirmation. Finance services accept commit=False for this transaction. No implicit buy funding.
- Voice: OpenRouter transcription, existing parser, persistent draft, explicit confirmation. OGG size/duration limits; audio in memory.
- GenBI: strict whitelisted AnalyticsSpec, bounded dates, account filter, confirmed RUB operations, Moscow dates, five report intents, backend Decimal calculations, chart and table in /analytics.
- Fixed credit fees being counted twice in category totals.
- Repaired an existing broken usage-event test to check committed data in an independent DB session.
- Optional AI_CA_FILE support for an already trusted local inspection CA. TLS verification remains enabled. Private config and machine-specific CA are ignored by Git; do not copy their contents here.
- Loopback ports, automatic migrations, restart policies, start.ps1/stop.ps1, README-MVP.md, active AI navigation links.

## Verification

Latest evidence: logs/pytest-miniapp.txt (262 tests), logs/genbi-live-repeat.txt, logs/frontend-build-miniapp-final.txt, logs/live-miniapp.txt, logs/miniapp-browser.txt and logs/miniapp-public-browser.txt. All passed. Prior MVP evidence remains in logs/pytest-mvp.txt (226 tests), logs/frontend-build-mvp.txt, logs/live-ai-mvp.txt and logs/browser-check.txt. Verify current files and outputs before reporting status.

Real provider smoke ran in the separate finance_ai_smoke DB with synthetic speech and operations. Main ledger remained empty after a real Telegram voice draft was cancelled by the user. Do not include account identifiers or message contents in handoff notes.

## Runtime

Compose project finance-ai-service, ports 3000/8000/5432 and gateway 8080 on loopback. Main PostgreSQL persists in finance-ai-service_postgres_data. Start local web with start.ps1; Mini App with start-miniapp.ps1 or start.ps1 -MiniApp; stop with stop.ps1. Never remove volumes to fix frontend cache. Production frontend builds on start, then runs next start (Next 14.2.35).

The full web MVP retains dev auth and stays local. A restricted public Mini App gateway and temporary HTTPS tunnel are running. Telegram binding was completed by the user. An initial cash account was created without financial operations. Local synthetic audio and browser QA tooling are ignored. Main ledger count was zero after implementation and automated QA; read current count if needed because the user may start using it.

## Limits

GenBI has no market-price history, PnL ranking, forecasts or arbitrary SQL/filters. Allocation is book cost with manual valuations, not market price. Budget semantics are documented in README-MVP.md. Expenses may overdraw; buys/transfers through Telegram require funds.

The existing web parser records usage counts but not exact provider cost. GenBI/STT record returned cost; use provider-side limits for a hard cap. Public access is limited to Mini App routes with Telegram auth, not full web auth. Do not claim a complete tax engine or liability accounting.

## Workspace integrity

The repository already had substantial modified/untracked work and a deleted historical log before this task. The user requested saving all current work in Git and creating the remote through the CLI. Commit 66b9254 captures the MVP. Private GitHub repository https://github.com/2303850Analyst/finance-ai-service was created with gh; origin/master tracks master. Environment files, local CA, runtime URLs and raw logs stay local; compact verification reports are included. Verify current files, Git history, running services and tests over these notes.

## Telegram Mini App continuation

The user requested implementing a Telegram Mini App and explicitly invoked gstack-plan-design-review. All seven design passes and choices D1-D12 are complete. D12 authorized one mock refresh followed by implementation; do not repeat design approvals. Approved layout A (overview first, bottom tabs) + palette C; editable AI draft fields; automatic confirmation recovery; GenBI follow-up context; in-app voice with bot fallback; Mini App-specific styles; keyboard-aware navigation; temporary HTTPS from this computer with local database.

The current plan is C:/Users/i/.gstack/projects/finance-ai-service/plans/telegram-mini-app.md. Review state is C:/Users/i/.gstack/projects/finance-ai-service/telegram-mini-app-review-state.json. Design artifacts, approved.json, DESIGN.md and responsive-audit.json are under C:/Users/i/.gstack/projects/finance-ai-service/designs/telegram-mini-app-20261113. The local preview server used port 61662; verify that it is still running before referencing its URL.

Updated mock: reviewed-board.html/reviewed.html and reviewed-board.png. Its 42 refreshed layout checks passed. Design review was logged with gstack-review-log and read back; initial 3/10 -> 9/10, 12 decisions, zero unresolved. The plan's final review report describes the design-stage result, not a completed separate engineering skill invocation. No separate gstack-plan-eng-review was invoked; implementation received code inspection and actual tests below.

Implemented Mini App:

- backend/app/services/miniapp_auth.py verifies Telegram HMAC, age <=3600 seconds and bound active owner, no dev fallback. All /api/v1/miniapp routes use it, responses are no-store.
- miniapp_service.py provides overview/history using existing Decimal engines, account creation, pending drafts, editable revisioned drafts, WebM/MP4/WAV -> OGG via bounded ffmpeg subprocess and synthetic-idempotent parse requests.
- Migration 20261113_miniapp adds draft revision. Bot callback buttons include revision; stale old buttons reject edited drafts. Confirmation and cancellation lock the shared row; financial write and status commit atomically. Status reads also lock to wait for ongoing confirmation.
- GenBI supports validated context changes and backend series totals. Follow-ups retain unspecified type/account/date filters. Five existing report intents reused.
- frontend/src/components/miniapp contains mobile shell, draft editor/preview, voice recorder and GenBI. /miniapp bypasses desktop shell, light/dark local Golos fonts. Recovery stores only draft ID locally, checks on reopen/online/activation. Keyboard detection hides tabs. 320/390/768 layouts checked, not equivalent to physical-phone acceptance.
- deploy/miniapp.conf publishes only /miniapp, static assets and protected Mini App API. Other APIs/docs/seed/internal bot paths return404. cloudflared profile provides HTTPS. start-miniapp.ps1 checks both local/public isolation and configures bound user's bot menu via app.configure_miniapp without sending messages. Current address is in ignored .miniapp-runtime.json; do not hardcode it into app source. Run start-miniapp.ps1 after tunnel restarts to update the menu.

Validation completed:

- 255 backend tests passed, including invalid/expired signatures, owner isolation, draft versions, cross-transport concurrent confirmation, audio conversion, transfer/account filters, Moscow date boundaries and all five report modules. Allocation fixtures follow AGENTS.md: buy amount grows position cost; trade fee is a separate investment expense. The final category/source length limits match DB columns; runtime restarted and public/local UI checks passed after those changes.
- Production build passed, Mini App approximately 102 kB first-load JS.
- .qa/miniapp-check.cjs passed through both loopback gateway and public HTTPS: edit, preserved confirmation error, lost-response and reopen recovery, contextual GenBI/table, changed history filters, actual browser MediaRecorder with synthetic device, mic-denial fallback, empty account. SDK and API finance data are fixtures; no personal data in screenshots.
- tests/live_miniapp_smoke.py passed with real AI in separate finance_ai_smoke DB: synthetic MP4 speech -> parse -> edit450to475 -> exactly one confirmed operation, real GenBI and prior-month follow-up preserving account/type. Main ledger untouched.
- Actual Telegram menu set and read back. Public no-auth API401 and local API404 verified. At this checkpoint six services are running.

Phone follow-up: the user followed their own scenario and confirmed an operation. Successful Mini App authentication, transcription, parsing, draft revision and confirmation are verified in actual service events. Real user data now exists; do not remove or rewrite it as a test cleanup. No personal financial details are recorded here. Physical keyboard behavior remains unverified.

The user's analytics question was rejected by the keyword guard because it omitted the Russian money stem and the ё spelling of report. Reproduced with the interface's own suggested question. Added those finance signals while retaining higher-priority block checks, plus six classifier/API regression cases. All 261 tests passed; backend restarted. Replayed the exact question through the live analytics endpoint with the real AI and verified its report against the ledger, without changing financial data. No further design approvals are needed.

Second GenBI follow-up: user then reported a different 422 on the same question. Logs showed a preset had been opened first. Live provider probe reproduced it twice: with matching context the model correctly returns {"changes":{}}, but backend rejected an empty change set. The earlier fresh-report smoke did not cover this sequence. Added a preset -> repeated-question API regression (with and without account filter), observed both fail with the user's exact message, then allowed valid empty changes to reuse the validated context and clarified the planner prompt. Unknown keys, incomplete date changes, unsupported and clarification responses remain rejected. Full suite now 262 passed. Backend restarted before final verification. .qa/genbi-live-repeat.cjs drove the production Mini App UI with fixture SDK/bootstrap/preset and real local analytics API/AI for two repeated questions; both200, context preserved, no page errors. Logs/genbi-repeat-regression-before.txt and after.txt capture red/green results. Probe used temporary in-process wrapping only; no debug logging remains in application code. No financial writes during diagnosis.

Third GenBI report showed an empty previous-month result. API succeeded; the replaced result remained above the viewport and the input placeholder looked like a submitted question. Reproduced the viewport failure before editing. GenBI now focuses/scrolls to the result, displays the submitted question, shows zero totals and an explicit empty period, and offers a current-month report preserving type/account. Empty tables are hidden and input examples are separated from the placeholder. tests/ui/genbi-result-check.cjs passed on loopback and the current public HTTPS address with synthetic SDK/API data. Production build and existing Mini App browser regression passed; frontend restarted. Users must close/reopen the Mini App to load this frontend revision. No financial writes or calculation changes.
