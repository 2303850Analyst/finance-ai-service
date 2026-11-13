# Stage 1 — Foundation

← [[04_Roadmap]] | [[01_Dev_Log]]

**Статус:** ✅ Закоммичен
**Git commit:** `Stage 1: project foundation and core database schema`

## Что реализовано

### Структура
```
finance-ai-service/
├── backend/
│   ├── app/
│   │   ├── api/health.py
│   │   ├── models/          # user, account, asset, operation, position, audit_log
│   │   ├── config.py        # Pydantic settings
│   │   ├── database.py      # async engine + Base
│   │   └── main.py          # FastAPI app
│   ├── alembic/
│   │   └── versions/a1b2c3d4e5f6_create_core_domain_tables.py
│   └── requirements.txt
├── frontend/src/app/
│   ├── page.tsx             # Dashboard + health check
│   └── layout.tsx
└── docker-compose.yml
```

### DB Schema

| Таблица | Ключевые поля |
|---|---|
| `users` | id, email, username, hashed_password, is_active |
| `accounts` | id, user_id, name, account_type, currency |
| `assets` | id, ticker, name, asset_type, currency |
| `operations` | id, user_id, account_id, asset_id, type, status, amount, operated_at |
| `positions` | id, account_id, asset_id, quantity, average_price |
| `audit_logs` | id, user_id, action, entity_type, entity_id, details |

### Enum-типы

| Тип | Значения |
|---|---|
| `accounttype` | broker, bank, crypto, cash, deposit, other |
| `assettype` | stock, bond, etf, currency, cash, deposit, crypto, real_estate, other |
| `operationtype` | buy, sell, deposit, withdraw, dividend, coupon, fee, tax, manual_valuation |
| `operationstatus` | pending, confirmed, cancelled, rejected |

## Endpoints
- `GET /` — root
- `GET /api/v1/health` — статус API + БД
- `GET /docs` — Swagger UI

## Как запустить
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
```

## Известные нюансы
- Enum-типы создаются через `DO block` → [[03_ADR#ADR-004]]
- Alembic — async через `asyncio.run` в `env.py`
- Auth **не реализован** — добавляется в Stage 2
