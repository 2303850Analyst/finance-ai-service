# Dev Log

← [[00_Project_Index]]

## Stage 1 — Foundation
**Дата:** 2026-05-08
**Статус:** ✅ Закоммичен

### Что сделано
- Monorepo: `backend/`, `frontend/`, `docker-compose.yml`
- FastAPI + Pydantic settings + CORS
- SQLAlchemy 2 async + asyncpg
- Alembic setup (async `env.py`)
- Таблицы: `users`, `accounts`, `assets`, `operations`, `positions`, `audit_logs`
- Enum-типы: `accounttype`, `assettype`, `operationtype`, `operationstatus`
- Next.js 14 (App Router) + Tailwind
- Docker Compose: postgres, backend, frontend
- Health endpoint `/api/v1/health`
- Swagger UI на `/docs`

### Проблемы и решения

**Проблема 1:** После первого `alembic upgrade head` — только `alembic_version`, таблиц нет.
**Причина:** Папка `alembic/versions/` была пустой — revision-файл не был создан.
**Решение:** Создали вручную `a1b2c3d4e5f6_create_core_domain_tables.py`.

**Проблема 2:** `asyncpg.exceptions.DuplicateObjectError: type "assettype" already exists`
**Причина:** Предыдущий упавший прогон частично создал enum-типы. `CREATE TYPE` без guard упал при повторном запуске.
**Решение:** Заменили на `DO $$ BEGIN CREATE TYPE ...; EXCEPTION WHEN duplicate_object THEN NULL; END $$`

**Проблема 3:** SQLAlchemy пытался создать enum-типы повторно при `op.create_table`.
**Причина:** `sa.Enum(name=..., create_type=False)` не гарантирует подавление DDL в PostgreSQL.
**Решение:** Заменили на `postgresql.ENUM(name=..., create_type=False)` из `sqlalchemy.dialects`.

**Финальный порядок сброса и применения:**
```bash
docker compose down -v
docker compose up --build -d
docker compose exec backend alembic upgrade head
```

---

## Stage 2 — Portfolio Engine
**Дата:** 2026-05-08
**Статус:** ✅ Готов к commit

→ [[06_Stage_2_Portfolio_Engine]]

---

## 2026-05-08, Stage 2 — Core Finance Domain and Portfolio Engine

### Сделано
- CRUD API: accounts, assets, operations (create, list, delete)
- Portfolio engine: пересчёт positions из confirmed operations
- Portfolio endpoints:
  - `GET /api/v1/portfolio/summary`
  - `GET /api/v1/portfolio/positions`
  - `GET /api/v1/portfolio/allocation`
- Seed dev data (`POST /api/v1/seed/dev-data`):
  - dev user: `dev@localhost`
  - accounts: Т-Инвестиции, Наличные
  - assets: SBER, YDEX, LKOH, RUB, USD, BTC
- Тесты: 6 unit-тестов portfolio engine + 8 интеграционных тестов

### Проверки
- `POST /api/v1/seed/dev-data` — работает, идемпотентен
- `GET /api/v1/accounts` — возвращает список счетов
- `GET /api/v1/assets` — возвращает список активов
- Swagger `/docs` — показывает все Stage 2 endpoints
- `pytest`: 14 passed

### Проблемы и решения

**Проблема:** Интеграционные тесты падали с asyncpg-ошибками:
- `RuntimeError: got Future attached to a different loop`
- `asyncpg InterfaceError: another operation is in progress`

**Причина:** `test_engine` (scope=module) создавал asyncpg-пул в одном event loop. `db`/`client` (scope=function) запускались в другом event loop.

**Решение:**
- Тестовая БД `finance_ai_test` создаётся/удаляется один раз через синхронный psycopg2 (scope=session, без event loop)
- Async engine и AsyncSession — function-scoped (новый engine на каждый тест, в том же loop)
- В `pytest.ini` добавлено: `asyncio_default_fixture_loop_scope = function`
- Добавлена зависимость `psycopg2-binary`

### Дополнительные фиксы
- `amount` для `buy`/`sell` теперь вычисляется автоматически как `quantity * price` (Pydantic model_validator). Клиентское значение игнорируется.
- `manual_valuation` теперь валидируется: требует `asset_id` и `price > 0`.

### Итог
[[06_Stage_2_Portfolio_Engine]] завершён.
Следующий шаг — [[04_Roadmap|Stage 3: Web Dashboard]].

---

## 2026-05-08, Stage 3 — Web Dashboard

### Сделано
- Реализован web dashboard на Next.js.
- Добавлена навигация: Dashboard, Operations, Accounts, Assets (sidebar + мобильный top bar).
- Добавлен API client (`src/lib/api.ts`) с `NEXT_PUBLIC_API_URL` и fallback на `localhost:8000`.
- Страница **Dashboard**:
  - portfolio summary cards (total value, positions count, API status, DB status)
  - positions table (ticker, qty, avg price, total cost)
  - recent operations table (дата, тип, asset ticker, qty, price, amount)
  - allocation chart через Recharts (donut, SSR-safe через `dynamic`)
  - кнопки Seed dev data и Refresh
- Страница **Operations**:
  - таблица операций с аккаунт/тикер lookup
  - форма создания (поля показываются в зависимости от типа)
  - удаление операции с пересчётом позиций
  - клиентские фильтры по type, account, asset
- Страницы **Accounts** и **Assets**: таблицы + формы создания.

### Проверки
- `pytest`: 14 passed (backend не изменялся)
- Frontend build успешен
- Seed dev data работает через UI
- Buy операция создаётся через форму
- Sell больше доступного показывает backend error в форме
- Delete операции → positions пересчитываются
- Recent Operations показывает ticker актива корректно

### Проблемы и фиксы
- **Asset column показывал `'—'`**: Dashboard не загружал assets. Исправлено — добавлен `api.assets.list()` в `loadAll`, построен `assetMap`.
- **Время формы было UTC**: `nowLocal()` вызывал `.toISOString()` (UTC). Исправлено через `getTimezoneOffset()`.
- **Устаревший `operated_at`**: `EMPTY_FORM` инициализировался при module load. Исправлено через lazy `useState`.
- **`fmt` давал NaN**: нет guard для невалидных чисел. Добавлен `isNaN` check.
- **Лишний conditional в `api.ts`**: `typeof window !== 'undefined'` с одинаковыми ветками. Упрощено.

### Ограничения (Stage 3 MVP)
- Нет пагинации таблиц
- `delete` использует `browser confirm()` диалог
- Dashboard не обновляется автоматически после действий на Operations странице — ручной Refresh
- Нет auth, AI, GenBI, Telegram

### Итог
Stage 3 готов к commit.
Следующий шаг — [[04_Roadmap|Stage 4: AI Command Bar]].

---

## 2026-05-09, Stage 4 — AI Command Bar + Expense + Budget + Cash Flow

### Сделано
- **AI Command Bar**: MockProvider + OpenAICompatibleProvider, парсинг текста → OperationDraft → подтверждение пользователем
- **Scope Guard** (`ai_scope_guard.py`): блокирует investment advice, jailbreak, out-of-scope запросы
- **Cash balances**: `GET /api/v1/portfolio/cash-balances`, `calculate_all_cash_balances`
- **Interest engine**: ежедневный расчёт по остатку, `GET /api/v1/portfolio/interest-accruals`, `GET /api/v1/portfolio/deposits`
- **Budget engine**: `GET /api/v1/budget/summary` — income, living/investment/credit expenses, free cashflow
- **Expenses**: операция `expense` с группами `living / investment / credit`, категориями, merchant
- **Deposit modal**: создание вклада через Assets → "+ Создать вклад" (account + operation + interest settings в 3 шага)
- **Recurring income**: `POST /api/v1/budget/recurring-income`, `GET /api/v1/budget/salary-due` → SalaryWidget на Dashboard
- **Transfer**: `POST /api/v1/operations/transfer`, TransferModal на Dashboard, отображение в Operations
- **NDFL prompt**: после sell → NdflModal с FIFO себестоимостью
- **Deposit close**: DepositCloseModal из Assets → перевод principal (не accrued interest!)
- **IncomeModal, ExpenseModal**: на Dashboard
- Тесты: 182 passed

### Ключевые финансовые правила (финально верифицированы)
- Transfer — не доход и не расход. Общий капитал уменьшается только на fee.
- `deposit` + `income_source` = Доход; без income_source = Пополнение; `[auto_funding]` = Автопополнение.
- НДФЛ = 13% от прибыли (FIFO себестоимость), не от суммы продажи.
- Deposit close = перевод principal only. Accrued interest — производная величина, отдельная операция.
- New Account форма не включает `deposit` как тип (вклады создаются через Assets).
- Transfer в New Operation dropdown недоступен (используй кнопку "Перевод" на Dashboard).

### Проблемы и фиксы
- `uuid_generate_v4() does not exist` → заменено на `gen_random_uuid()` (PostgreSQL 13+ built-in)
- NDFL ошибочно считался 13% от суммы продажи → исправлено: FIFO с fallback на 0 + amber warning
- Deposit close включал accrued_interest → исправлено: только principal
- Next.js `Cannot find module './755.js'` → docker volume isolation (`/app/.next` anonymous volume)
- Transfer UI не показывал "Откуда/Куда" и баланс → добавлены метки, доступный остаток, блок при превышении

---

## 2026-05-09, Stage 5 — Consistency review and UX fixes

### Сделано
- **Interest UI**: инфо-блок теперь показывает выбранный период выплаты (reactive, не static "ежедневно"). Добавлена helper text: "Расчётная база: ежедневный остаток. Период выплаты определяет, когда проценты зачисляются."
- **Edit deposit**: в DepositsSection (Assets page) добавлена кнопка "% ставка" → EditDepositModal для редактирования rate, payout_frequency, capitalization, дат
- **Delete deposit**: кнопка "✕" с подтверждением → `DELETE /accounts/{id}` (заблокировано бэкендом если есть операции, 409)
- **Transfer in New Operation form**: операция `transfer` убрана из dropdown; пользователь должен использовать кнопку "Перевод" на Dashboard
- **Terminology fix**: фильтр типа операций в Operations page использует читаемые метки (Доход, Расход, Перевод)
- **Тесты**: +11 тестов → 182 passed. Новые тесты: delete guards (account/asset/deposit), payout_frequency round-trip, transfer response format

### Закрытые вопросы
- ✅ Период выплаты процентов — теперь отображается корректно в обоих UI (создание и настройка)
- ✅ Удаление вкладов безопасно заблокировано бэкендом
- ✅ Редактирование настроек вклада доступно со страницы Assets

---

## 2026-05-09, Extra consistency scope

### Сделано
- **UI labels**: унифицированы русские метки для всех типов операций во всех компонентах:
  - `OP_TYPE_LABELS` в `page.tsx` (Dashboard): добавлены buy→Покупка, sell→Продажа, withdraw→Вывод, dividend→Дивиденды, coupon→Купон, fee→Комиссия, tax→Налог, manual_valuation→Переоценка
  - `OP_LABELS` и `EXPENSE_GROUP_LABELS` в `operations/page.tsx`: полная русская карта
- **Empty states**: добавлены компактные заглушки вместо скрытия блоков:
  - Cash Balances (Dashboard): "Нет остатков. Создайте счёт и добавьте операцию пополнения." (блок теперь всегда виден после загрузки)
  - Deposits (Assets page): "Нет активных вкладов. Нажмите «Создать вклад» чтобы добавить."
  - Assets table (Assets page): "Нет активов. Создайте актив или загрузите тестовые данные." (была EN)
- **Assets count label**: "total" → "шт." (консистентно с Deposits)
- **CLAUDE.md**: добавлены Operation Routing Matrix и Note про Next.js cache rebuild
- **Тест**: `test_transfer_fee_reduces_total_capital_by_fee_only` уже присутствовал в `test_transfer.py` — финансовый инвариант подтверждён

### Финальный статус
- 182 тестов passed (тесты не менялись, новые не нужны)
- Готово к commit: Stages 4 + 5
