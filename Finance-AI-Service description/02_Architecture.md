# Architecture

← [[00_Project_Index]]

## Стек

| Слой | Технология |
|---|---|
| Backend | Python 3.12, FastAPI |
| ORM | SQLAlchemy 2 (async) |
| Migrations | Alembic |
| DB | PostgreSQL 16 |
| Frontend | Next.js 14, TypeScript, Tailwind |
| AI | Провайдер-абстракция (mock / OpenAI-compatible) |
| Telegram | aiogram 3 |
| Deploy | Docker Compose |

## Модули

```
backend/app/
├── api/           # Route handlers
├── models/        # SQLAlchemy models
├── schemas/       # Pydantic schemas (запланировано)
├── services/      # Бизнес-логика (запланировано)
├── portfolio/     # Portfolio Engine (Stage 2)
├── ai/            # AI Parser + провайдер-абстракция (Stage 4)
├── genbi/         # GenBI v1 (Stage 5)
└── telegram/      # Telegram integration (Stage 6)
```

## Схема БД

```
users ──< accounts ──< operations >── assets
                  └──< positions >──┘
users ──< audit_logs
```

## Потоки данных

### Ввод операции (Web)
```
User → Frontend → POST /operations (pending)
     → AI Parser (опционально) → предложение
     → User подтверждает → status: confirmed
     → Portfolio Engine пересчитывает positions
```

### Ввод операции (Telegram)
```
User → Telegram Bot → aiogram handler
     → Backend API (pending)
     → Уведомление с кнопкой подтверждения
     → User подтверждает → confirmed
```

### GenBI запрос
```
User question → AI → analytics spec (JSON)
             → Analytics Engine → SQL + расчёт
             → Frontend → chart / KPI / table
```

## Ключевые принципы
- AI **не пишет** напрямую в БД
- Portfolio state = результат пересчёта из `operations`
- Никаких инвестиционных советов
- Никакой автоторговли

→ [[03_ADR]] | [[10_Open_Questions]]
