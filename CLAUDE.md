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
- `accounttype`: broker, bank, crypto, cash, deposit, other
- `assettype`: stock, bond, etf, currency, cash, deposit, crypto, real_estate, other
- `operationtype`: buy, sell, deposit, withdraw, dividend, coupon, fee, tax, manual_valuation
- `operationstatus`: pending, confirmed, cancelled, rejected

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

## Stage 2 Constraints

- No Auth — use a temporary dev user dependency or seed user
- No Telegram
- No GenBI
- No real AI provider
- Business logic in `services/`, not in route handlers
