# Roadmap

← [[00_Project_Index]]

## Этапы

| # | Название | Статус |
|---|---|---|
| 1 | [[05_Stage_1_Foundation\|Foundation]] | ✅ Готово |
| 2 | [[06_Stage_2_Portfolio_Engine\|Portfolio Engine]] | ✅ Готово |
| 3 | Web Dashboard | ✅ Готово |
| 4 | AI Command Bar + Expense + Budget + Cash Flow | ✅ Готово (182 тестов) |
| 5 | Consistency review & UX fixes | ✅ Готово |
| 6 | [[07_GenBI_Module\|GenBI v1]] | 🔲 Запланирован |
| 7 | [[08_Telegram_Integration\|Telegram Integration]] | 🔲 Запланирован |
| 8 | Import & Market Data | 🔲 Запланирован |

---

## Stage 1 — Foundation ✅
- Monorepo, Docker Compose
- FastAPI, PostgreSQL, SQLAlchemy 2, Alembic
- DB schema: users, accounts, assets, operations, positions, audit_logs
- Next.js frontend, health check

## Stage 2 — Portfolio Engine ✅
- CRUD: accounts, assets, operations (без auth — dev user)
- Portfolio Engine: пересчёт positions из confirmed operations
- Pydantic schemas для всех сущностей
- API: `/portfolio/summary`, `/portfolio/positions`, `/portfolio/allocation`
- Seed endpoint: dev user, accounts, assets
- Тесты: 14 passed

## Stage 3 — Web Dashboard ✅
Цель: web-интерфейс, пригодный для ручной работы с портфелем.

- Страница Dashboard: summary cards, positions table, allocation donut chart, recent operations
- Страница Operations: таблица с фильтрами, форма создания (поля по типу), удаление с пересчётом
- Страница Accounts: таблица + форма создания
- Страница Assets: таблица + форма создания
- API client (`lib/api.ts`) с `NEXT_PUBLIC_API_URL` fallback
- Recharts AllocationChart (SSR-safe через `dynamic`)
- Sidebar навигация (desktop) + top bar (mobile)
- Тесты: 14 passed (backend без изменений)

## Stage 4 — AI Command Bar ▶️
Цель: пользователь вводит текст → AI парсит → предлагает черновик операции → пользователь подтверждает → операция сохраняется.

- Provider abstraction (MockProvider + OpenAI-compatible)
- AI парсит текстовый ввод → `OperationProposal` (не пишет в БД напрямую)
- Backend валидирует proposal перед сохранением
- Frontend: поле ввода + превью предложенной операции + кнопка подтверждения
- Audit log записывает каждое AI-предложение
- → [[09_AI_Parser]]

## Stage 5 — GenBI v1 🔲
- AI конвертирует вопрос → analytics spec (JSON)
- Analytics Engine выполняет расчёт из БД
- Frontend рендерит: line, bar, donut, KPI, table
- → [[07_GenBI_Module]]

## Stage 6 — Telegram Integration 🔲
- aiogram 3 bot
- Быстрый ввод операции текстом
- Подтверждение через inline-кнопку
- Уведомления о статусе операций
- → [[08_Telegram_Integration]]

## Stage 7 — Import & Market Data 🔲
- Импорт из CSV (брокерские отчёты)
- Market data: котировки активов
- Пересчёт portfolio value с рыночными ценами
- Исторические цены для графиков
