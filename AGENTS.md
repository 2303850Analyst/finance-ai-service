# Finance AI Service

Browser-based AI service for personal finance and investment portfolio tracking.
Primary interface: Web App. Secondary: Telegram Bot (quick input + notifications).

## Core Rules

- Backend owns all business logic. Frontend and Telegram are adapters only.
- AI never writes directly to the database.
- Every AI-parsed operation requires user confirmation before being written.
- Operation history is the source of truth.
- Portfolio state is always recalculated from operations — never stored directly.
- No investment advice. No auto-trading.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL, Pydantic |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Recharts |
| Telegram | aiogram 3 |
| AI | Provider abstraction — `MockProvider` + `OpenAICompatibleProvider` |
| Deploy | Docker Compose |

## Project Structure

```
finance-ai-service/
├── backend/
│   ├── app/
│   │   ├── api/        # Route handlers only — no business logic
│   │   ├── models/     # SQLAlchemy models
│   │   ├── schemas/    # Pydantic I/O schemas
│   │   ├── services/   # All business logic lives here
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   └── alembic/
├── frontend/
│   └── src/app/
└── docker-compose.yml
```

## DB Schema (Stage 1)

Tables: `users`, `accounts`, `assets`, `operations`, `positions`, `audit_logs`

Enums:
- `accounttype`: broker, bank, crypto, cash, deposit, savings, other
- `assettype`: stock, bond, etf, currency, cash, deposit, crypto, real_estate, **vehicle**, **other_physical**, other
- `operationtype`: buy, sell, deposit, withdraw, dividend, coupon, fee, tax, manual_valuation, **expense**, **transfer**
- `operationstatus`: pending, confirmed, cancelled, rejected

Notable columns:
- `operations.linked_asset_id` — nullable FK to `assets.id` (SET NULL on delete). Used for credit payment → asset link.

> Enum DDL: always `DO $$ BEGIN CREATE TYPE ...; EXCEPTION WHEN duplicate_object THEN NULL; END $$`
> Enum columns: always `postgresql.ENUM(name=..., create_type=False)`

## Current Status

Stage 1 complete and committed.
- `localhost:3000` — frontend
- `localhost:8000/docs` — Swagger
- `docker compose exec backend alembic upgrade head` — apply migrations

## Stage Order

1. **Foundation** ✅
2. **Core finance domain + portfolio engine** ← next
3. Web dashboard
4. AI command bar
5. GenBI v1
6. Telegram integration
7. Import and market data

## Finance Domain Rules

These rules define correct financial behavior. All stages must follow them.
Rules marked **Future rule** must not be implemented until explicitly scheduled.

### 1. Operation history is source of truth
Cash balances and asset positions must always be derived from confirmed operations.
Never store computed state (balance, position) as primary data.

### 2. Income, funding and auto-funding are different
- **Доход** — increases user's total capital (salary, bonus, dividends from outside).
- **Пополнение / funding** — moving user's own money to an account. Does not increase capital.
- **Transfer** — moving money between own accounts. Does not increase capital.
- **Auto-funding** — a technical deposit created to enable a buy when cash is insufficient.
  Created only after explicit user confirmation. Note: `[auto_funding]`, `income_source: null`.

### 3. `deposit` operation type ≠ always "Доход" in UI
The `deposit` backend type covers multiple meanings. UI label depends on context:
- `deposit` + `income_source` set → **Доход**
- `deposit` + `note = "[auto_funding]"` → **Автопополнение**
- `deposit` with no `income_source` → **Пополнение**
Do not label every deposit as Доход.

### 4. Salary and recurring income (Future rule)
- Salary can be configured as planned monthly income.
- Must not be created silently — user must confirm each month.
- Dashboard shows "Получил зарплату?" confirmation with editable amount.
- Operation created only after confirmation.

### 5. Transfers
- Moving money between own accounts (bank → broker) is a transfer, not income and not expense.
- Model: single Operation row with `operation_type=transfer`, `account_id=from`, `to_account_id=to`.
- Cash engine: `from_account -= (amount + fee)`, `to_account += amount`. Net capital change = `-fee` only.
- Budget engine: transfers are excluded from every income/expense bucket.
- **Validation rule**: `amount + fee` must not exceed source account cash balance.
  Transfers must not create negative cash. Expenses may go negative; transfers must not.
  Backend returns HTTP 400 "Insufficient funds" if violated.
- `fee` is the only capital-reducing cost in a transfer.
- UI: "Откуда" / "Куда" labels; show current balance in account selector; "Доступно: X RUB" hint.

### 6. Auto-funding flow
- Buy requires sufficient cash balance.
- If cash is insufficient → return `funding_required`, do not save the buy.
- User must confirm auto-funding explicitly.
- After confirmation: create `deposit` (amount = missing cash, `note = "[auto_funding]"`) + `buy` atomically.
- Deposit fee from funding is separate from trade fee.

### 7. Fees
- Fees permanently reduce money.
- Trade fee → belongs to the buy/sell operation.
- Deposit fee → belongs to the funding/deposit operation.
- Withdraw fee → belongs to the withdraw operation.
- Do not mix fee types in UI text.

### 8. Sell and НДФЛ
- After a sell operation, show NDFL prompt (NdflModal on Operations page).
- НДФЛ is on **profit**, not on full sale proceeds. Never default to 13% of proceeds.
- Correct formula: `tax_base = sell_proceeds − proportional_cost_basis − sell_fee`; `default_ndfl = max(tax_base, 0) × 13%`
- **FIFO cost basis**: compute using all confirmed buy/sell operations for the same asset, ordered
  chronologically. Replay buys as lot pushes and prior sells as lot pops to get the FIFO queue at
  the moment of this sell. Consume sellQty lots; sum = cost basis.
  Example: buy 10@300, buy 10@400, sell 10@500 → FIFO cost = 3000, profit = 2000, NDFL = 260.
- If FIFO queue does not have enough lots (missing history): `default_ndfl = 0`,
  show: "НДФЛ считается с прибыли, а не со всей суммы продажи. Введите сумму вручную."
- User can edit the tax amount before confirming.
- Tax operation is created only after explicit user confirmation. Never auto-save.
- This is a preliminary estimate only — not a full Russian tax engine.
- Do not implement: tax residency, exemptions, 3-year/5-year льгота, broker tax agent logic.

### 9. Capital vs Portfolio value
- `Total capital = cash balances + asset positions value + deposits/savings + custom assets`
- Portfolio value (investment assets only) ≠ total capital.
- Dashboard should eventually break capital into: cash / investment assets / deposits & savings / other assets.

### 10. RUB-only for now
- Current MVP assumes RUB operations.
- Do not implement partial multi-currency logic.
- Foreign stocks and FX conversion are future stages.

### 11. Unrealized PnL
- Unrealized PnL is not income.
- Income = actual cash inflow.
- Realized PnL appears only after selling an asset.
- Market price changes are valuation changes, not income.

### 12. Manual valuation
- `manual_valuation` does not affect cash or quantity.
- Used for illiquid assets without market price.
- Future: should move to a `market_prices` or `valuation_history` table.

### 13. Deposits and savings (partial Future rule)
- Interest is calculated on report date (segment algorithm), not created as daily operations.
- Bank deposit has `interest_end_date`; after that, interest stops accruing.
- Moving deposit principal to cash requires user confirmation ("Закрыть вклад") — **Future rule**.
- `savings` account has daily interest with optional capitalization.
- Manual income source `interest` is allowed only for actual payouts or corrections.
  IncomeModal shows a warning when `income_source = 'interest'`.

### 14. Expenses (Future module)
- Expense decreases cash.
- Expense has categories and merchant.
- Expenses do not affect asset positions.
- Separate from investment operations.

### 15. Asset sale vs income
- "Продажа имущества вне учёта" → income (use `income_source = 'sale'`).
- If the asset is already tracked in the system → must use a `sell` operation, not income.
- Prevents double-counting.

### 16. Crypto / DEX (ignored for now)
- Do not implement DEX, on-chain positions, contract addresses in current stages.

### 17. AI safety
- AI produces drafts only. AI never writes directly to the database.
- Every AI-parsed operation requires explicit user confirmation before being saved.
- Backend validates all data independently before persisting.

### 18. AI Scope Guard
- `app/services/ai_scope_guard.py` — rule-based classifier runs before any AI provider call.
- Returns `ALLOWED`, `BLOCKED`, or `NEEDS_CLARIFICATION`.
- If `BLOCKED`: AI provider is **not called**; safe response returned immediately:
  `"Я отвечаю только по вашему финансовому учёту, портфелю, операциям и функциям сервиса."`
- **Blocked categories** (in priority order):
  1. `prompt_injection` — "ignore previous instructions", jailbreak, DAN mode, bypass/disable filters
  2. `system_prompt_request` — requests to reveal/repeat system prompt or instructions
  3. `investment_advice` — "what should I buy", "recommend stocks", "куда вложить деньги"
  4. `illegal_request` — tax evasion, money laundering
  5. `out_of_scope` — no finance/service keywords found (weather, recipes, general knowledge)
- **Allowed** if finance/service keywords detected: operations, portfolio, accounts, assets, deposits,
  interest, taxes (within service), income, navigation (добавить/create/show/etc.)
- The guard is a defense-in-depth layer only. Backend validation, auth, and user confirmation
  remain mandatory regardless of guard result.
- Prompt injection is an explicit, documented risk. All AI inputs are validated by the guard
  before reaching the AI layer.

---

## Capital Model

### Total Capital vs Portfolio Value
These are DIFFERENT metrics — do not mix them.

- **Portfolio value** (`Инвестпортфель`): cost basis of investment positions only.
  Source: `GET /api/v1/portfolio/summary → total_cost`.

- **Total capital** (`Общий капитал`): everything the user owns.
  Formula (MVP): `total_capital = cash_balances_total + investment_positions_total`
  - `cash_balances_total` = sum of all account cash balances (derived from operations)
  - `investment_positions_total` = portfolio total_cost

### No double-counting of deposits/savings
Cash balances represent money NOT yet invested. Portfolio total_cost represents money already invested.
A `buy` operation drains cash by `(amount + fee)` and grows positions by `amount` — they are complementary.
Deposit accounts (вклады) appear as cash balances (their principal), not as portfolio positions.
Therefore `cash + positions` never double-counts.

### Monthly cashflow ≠ Total capital
- "Денежный поток месяца" (budget summary) shows income, expenses, free cashflow for the period.
- It does NOT represent capital. Cashflow is a flow; capital is a stock.

### Current limitations (TODO)
- **Liabilities not modelled**: credit principal currently reduces cash without creating a liability.
  Full capital formula should be `total_capital = assets - liabilities`, but liabilities module is future work.
  Credit principal payments therefore appear to reduce total capital (overstated impact).
  Future fix: principal payment → reduce liability balance, not just cash.
- **Market value not used**: portfolio total_cost is at acquisition cost, not current market price.
  Future: use market prices for unrealized P&L and mark-to-market capital.
- **RUB-only**: multi-currency capital aggregation is future work.

---

## Expense Domain Rules (Stage 2)

### Expense groups
- `living` — everyday spending; fee is extra on top; cash = -(amount + fee)
- `investment` — investment-related spending; fee is extra on top; cash = -(amount + fee)
- `credit` — loan/mortgage payment; fee is already inside amount (principal + interest + fee = amount); cash = -amount

### Credit payment fee rule
For credit expenses, `amount` is the full payment including fee.
Cash engine must use `balance - op.amount` only (not `- op.amount - fee`).
Fee subtraction for credit would double-count because fee is already in amount.

### Embedded fees (buy/sell/deposit/withdraw)
Embedded fee stored in `buy.fee`, `sell.fee` etc. is counted as derived investment expense in budget analytics.
Cash effect happens only once inside the parent operation — do NOT create a separate expense op for it.

### Expense corrections in MVP
- Refund as a separate linked operation is **future work** (not in MVP).
- In MVP, user corrects a mistake by deleting the expense operation from Operations page.
- `is_refund` field exists in the DB schema (migration applied) for future use.
- Do **not** expose `is_refund` in any UI form until the linked-refund feature is designed.
- TODO: Refunds will be implemented later as linked operations to original expenses.
  When implemented, a refund must reference the original operation and reverse only that amount.

### Operation edit
- Full edit of operations is future work. Delete is sufficient for Stage 2.
- TODO: Add edit capability for expense operations (category, amount, merchant, date).

## Stage 2 Constraints

- No Auth — use a temporary dev user dependency or seed user
- No Telegram
- No GenBI
- No real AI provider
- Business logic in `services/`, not in route handlers

---

## UI Conventions

### Global navigation and AI assistant
- **Layout structure**: `Sidebar` (nav only) | `AIAssistantBar` (top strip) + `main` (page content).
  - `app/layout.tsx` renders `<Sidebar>` then a flex-col wrapper containing `<AIAssistantBar>` and `<main>`.
- **Sidebar** (`src/components/Sidebar.tsx`): navigation links only, w-56.
  - Active sections: Dashboard (`/`), Operations (`/operations`), Accounts (`/accounts`), Assets (`/assets`).
  - Dim "Скоро" section (desktop only): Deposits (→ `/assets`), Cash Balances (→ `/`), Income (disabled), Settings (disabled).
  - No search input in sidebar.
- **AIAssistantBar** (`src/components/AIAssistantBar.tsx`): persistent horizontal strip at the top of all pages, above `<main>`.
  - Label: "AI‑помощник". Input placeholder: "Спросите по сервису или финансам…". Send button: disabled.
  - Hint: "AI‑навигация будет добавлена позже" (hidden on narrow screens).
  - Real AI is NOT implemented. This is a UI placeholder only.
- **Page content**: no `mx-auto` on page root divs — content is left-aligned inside main area.

### Interest terminology and UI
- **Calculation base**: always daily balance (`ежедневный остаток`). Not configurable.
- **Payout frequency** (`payout_frequency`): `daily` / `monthly` / `at_maturity` — when accrued interest is credited.
- Info block in `InterestModal` and `CreateDepositModal`:
  - Label: **"Период выплаты процентов"**
  - Value: **reactive** — shows selected `payout_frequency` label (Ежедневно / Ежемесячно / В конце срока)
  - Helper text: "Расчётная база: ежедневный остаток. Период выплаты определяет, когда проценты зачисляются."
  - Updates immediately when dropdown selection changes.
- Rate field: **"Ставка, % годовых"** — always an editable `<input type="number">`.
- Save uses `PUT /accounts/{id}/interest-settings` (upsert) — never creates duplicates.
- **Do NOT** show a static "ежедневно по остатку" as if it were the payout period — this is confusing.

### Deposits vs Accounts
- Deposits are created via **Assets page** ("Создать вклад" button), not via the Accounts page.
- The New Account form on the Accounts page does **not** include `deposit` as a type option.
- The `% ставка` button on the Accounts page is shown only for `savings` accounts.
- Deposit accounts that exist in the DB are displayed in both the Accounts table AND the Deposits section of Assets page.
- **Edit deposit settings**: "% ставка" button in DepositsSection (Assets page) → `EditDepositModal`.
  - Editable: annual_rate_percent, payout_frequency, capitalization, interest_start_date, interest_end_date.
  - Principal (amount) is NOT editable via this modal — it is defined by the deposit's operations.
- **Delete deposit**: "✕" button in DepositsSection → `DELETE /accounts/{id}`.
  - Blocked (HTTP 409) if the account has any operations (principal exists).
  - Safe to delete only if no operations (e.g. account created but never funded).
  - Closing a deposit ≠ deleting it. Use "Закрыть вклад" to transfer principal.

### Edit/Delete safety rules
- **Account delete**: `DELETE /accounts/{id}` — blocked (409) if account has any operations.
- **Asset delete**: `DELETE /assets/{id}` — blocked (409) if used in operations or positions.
- **Deposit delete**: same as account delete — blocked if principal deposit operation exists.
- Never cascade-delete financial history.
- Frontend shows a two-step confirmation ("Удалить? Да / Нет") before calling DELETE.
- Backend returns the full error message from HTTP 409 — frontend must display it.

### Transfer UI rules
- Transfer is created via two entry points:
  1. **"Перевод" button on Dashboard** → opens `TransferModal` (shared component in `src/components/TransferModal.tsx`)
  2. **"+ Перевод" button on Operations page** → opens same `TransferModal`
  3. **Operations page "New Operation" dropdown** → selecting `transfer` shows inline `TransferForm` (same fields, no modal)
- `TransferModal` labels: "Откуда *" / "Куда *" / "Сумма перевода *" / "Комиссия" (optional).
- Account selectors show current balance: `"{name} · {balance} RUB"`.
- "Доступно: X RUB" hint shown below the source account selector.
- Submit disabled and amount input red-bordered when `amount + fee > available_balance`.
- Operations page: transfer row shows `from → to` in Account column, `—` in Asset column.
- `TransferModal` is a shared component — used by Dashboard and Operations page.

### Operation routing matrix

| Operation type | Entry point | Backend endpoint |
|---|---|---|
| `buy` / `sell` | Operations page → New Operation form | `POST /api/v1/operations` |
| `deposit` (Доход) | Dashboard → "Ввести доход" → `IncomeModal` | `POST /api/v1/operations` |
| `deposit` (Пополнение) | Operations page → New Operation form | `POST /api/v1/operations` |
| `deposit` (Автопополнение) | Dashboard AI bar → auto-funding confirm flow | `POST /api/v1/operations/confirm-with-funding` |
| `expense` (Расход) | Dashboard → "Ввести расход" → `ExpenseModal` | `POST /api/v1/operations` |
| `transfer` | Dashboard → "Перевод" OR Operations page → "+ Перевод" OR inline form | `POST /api/v1/operations/transfer` |
| `dividend` / `coupon` | Operations page → New Operation form | `POST /api/v1/operations` |
| `fee` / `tax` | Operations page → New Operation form | `POST /api/v1/operations` |
| `manual_valuation` | Operations page → New Operation form | `POST /api/v1/operations` |
| `withdraw` | Operations page → New Operation form | `POST /api/v1/operations` |

Rules:
- `transfer` is available in the Operations page "New Operation" dropdown as of Stage 2 completion.
  When selected, an inline transfer form replaces the generic form.
- `deposit` created by AI auto-funding has `note="[auto_funding]"` and `income_source=null`.
- `deposit` created via IncomeModal always has `income_source` set.

### Operation edit (PATCH endpoints)

- `PATCH /api/v1/operations/transfer/{id}` — edits amount, fee, currency, date, note. **Must be registered BEFORE** `PATCH /{id}` in router.
- `PATCH /api/v1/operations/{id}` — edits expense and other operation types. Rejects `buy`/`sell` (cost basis integrity).
- Partial update pattern: only fields present in JSON body are updated (`payload.model_fields_set`).
- Transfer edit: reverses current transfer effect from source balance before checking new amount.
  Formula: `available = current_balance + op.amount + old_fee`.
- Buy/sell edit: returns HTTP 400 with helpful message — delete and recreate instead.
- `EditOperationModal` on Operations page is type-aware:
  - `buy`/`sell` → informational "not editable" block
  - `transfer` → read-only accounts + editable amount/fee/date/note
  - `expense` → full form + credit link selector
  - others → simple amount/currency/fee/date/note form

### Physical assets

- `AssetType` enum includes: `vehicle`, `other_physical` (added via migration).
- Physical types: `real_estate`, `vehicle`, `other_physical`, `other` — defined in `PHYSICAL_ASSET_TYPES` set (frontend and backend).
- For physical types: ticker is **optional/hidden**. Backend auto-generates `PHYS-{uuid8}` if not provided.
- Assets page (`/assets`): type dropdown comes first; ticker field hidden for physical types; info notice shown.
- Assets table: shows `авто` (italic) instead of PHYS-XXXXX ticker for physical types.
- Asset type labels in Russian: Акция, Облигация, ETF, Валюта, Наличные, Вклад, Крипто, Недвижимость, Автомобиль, Физ. актив, Другое.

### Credit payment linked asset

- `Operation.linked_asset_id` (nullable FK → `assets.id`, `ondelete=SET NULL`) — added via migration.
- ExpenseModal (Dashboard) and EditOperationModal (Operations page): for `expense_group=credit`, show a linked asset selector.
- `linked_asset_id` is optional — warning shown only if user opens the selector and leaves it empty.
- Operations page credit rows show: `🔗 {asset_name}` if linked asset set.
- Use case: mortgage payment linked to a real estate asset.

### Next.js cache rebuild (chunk ID mismatch)

If you see `Cannot find module './755.js'` or similar in the browser console after switching between
dev and production Docker images, it means the `.next` build cache has stale chunk IDs.

Fix:
```bash
# Option 1 — restart with fresh anonymous volume
docker compose down -v && docker compose up --build

# Option 2 — force rebuild inside running container
docker compose exec frontend rm -rf /app/.next
docker compose restart frontend
```

The `docker-compose.yml` already uses an anonymous volume for `/app/.next` to prevent this in
normal dev flow. The issue surfaces when you manually switch between `next dev` and `next build`
without restarting containers.
