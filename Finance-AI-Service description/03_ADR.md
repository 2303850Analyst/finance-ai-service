# Architecture Decision Records

← [[00_Project_Index]] | [[02_Architecture]]

---

## ADR-001: Web App как основной интерфейс
**Статус:** Принято
**Контекст:** Нужен полноценный интерфейс для работы с портфелем.
**Решение:** Web App (Next.js) — primary. Telegram — только быстрый ввод и уведомления.
**Последствия:** Вся бизнес-логика — на backend. Telegram не дублирует UI.

---

## ADR-002: AI никогда не пишет напрямую в БД
**Статус:** Принято
**Контекст:** Risk of AI errors corrupting financial data.
**Решение:** AI создаёт `pending` операцию. Запись в БД — только после подтверждения пользователем.
**Последствия:** Нужен UI/Telegram flow подтверждения. Audit log для всех AI-предложений.

---

## ADR-003: Portfolio state пересчитывается из операций
**Статус:** Принято
**Контекст:** Нужна единственная источник правды для портфеля.
**Решение:** Таблица `positions` — кэш. Пересчитывается из `operations` при каждом изменении.
**Последствия:** `positions` можно в любой момент пересобрать. Нет drift между операциями и портфелем.

---

## ADR-004: PostgreSQL enum — DO block + `postgresql.ENUM(create_type=False)`
**Статус:** Принято
**Контекст:** `CREATE TYPE` в PostgreSQL не поддерживает `IF NOT EXISTS`. При повторном прогоне падает с `DuplicateObjectError`. `sa.Enum` дублирует DDL при `op.create_table`.
**Решение:**
- Создание: `DO $$ BEGIN CREATE TYPE ...; EXCEPTION WHEN duplicate_object THEN NULL; END $$`
- Колонки в таблицах: `postgresql.ENUM(name=..., create_type=False)`
- Удаление: `DROP TYPE IF EXISTS ...`
**Последствия:** Миграции идемпотентны. Нет двойного DDL от SQLAlchemy.

---

## ADR-005: Async SQLAlchemy + asyncpg
**Статус:** Принято
**Контекст:** FastAPI — async. Нужен async ORM.
**Решение:** `create_async_engine` + `async_sessionmaker`. Alembic env через `asyncio.run`.
**Последствия:** Все сервисы и репозитории — async. Alembic нужен отдельный sync-wrapper в `env.py`.

---

## ADR-006: Provider abstraction для AI
**Статус:** Принято (реализация — Stage 4)
**Контекст:** Не привязываться к конкретному AI-провайдеру.
**Решение:** Интерфейс `AIProvider`. Реализации: `MockProvider`, `OpenAICompatibleProvider`.
**Последствия:** Легко менять провайдера. Mock позволяет разрабатывать без API-ключей.

---

## ADR-007: Изоляция тестовой БД для async SQLAlchemy тестов
**Статус:** Принято

**Контекст:**
Интеграционные тесты Stage 2 падали с asyncpg-ошибками:
- `RuntimeError: got Future attached to a different loop`
- `asyncpg InterfaceError: another operation is in progress`

Причина: `test_engine` (scope=module) создавал asyncpg-пул в module event loop. `db`/`client` (scope=function) запускались в другом function event loop. asyncpg connections привязаны к event loop в момент создания и не могут использоваться из другого loop.

**Решение:**
- Отдельная тестовая БД `finance_ai_test` — создаётся и удаляется один раз за сессию через синхронный psycopg2 (без event loop).
- `test_engine` — function-scoped async fixture: свежий engine на каждый тест, drop_all + create_all.
- `db` и `client` — function-scoped, живут в том же loop, что и engine.
- В `pytest.ini` задан `asyncio_default_fixture_loop_scope = function`.

**Последствия:**
- Тесты не трогают dev БД.
- asyncpg connections не пересекают границы event loop.
- Схема пересоздаётся на каждый тест — медленнее, но стабильнее. Для текущего MVP приемлемо.
