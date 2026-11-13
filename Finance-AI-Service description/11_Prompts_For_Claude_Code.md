# Prompts For Claude Code

← [[00_Project_Index]]

---

## Stage 2 — Portfolio Engine

```
Read backend/app/models/ and backend/alembic/versions/a1b2c3d4e5f6_create_core_domain_tables.py first.

Create only Stage 2 of finance-ai-service.

Stage 2 goal:
Add auth, CRUD for core entities, and a basic portfolio engine.

Do not implement GenBI.
Do not implement Telegram.
Do not implement AI parser.
Do not implement market data.

Need:

1. Auth:
   - POST /api/v1/auth/register (email, username, password)
   - POST /api/v1/auth/login → { access_token, token_type }
   - JWT with python-jose, 30 min expiry
   - Password hashing with passlib[bcrypt]
   - Dependency get_current_user for protected routes

2. Pydantic schemas (backend/app/schemas/):
   - UserCreate, UserOut
   - AccountCreate, AccountOut
   - AssetCreate, AssetOut
   - OperationCreate, OperationOut
   - PositionOut
   - PortfolioSummary

3. Service layer (backend/app/services/):
   - user_service.py: create_user, get_by_email
   - account_service.py: create, list_by_user
   - asset_service.py: create, get_by_ticker, list
   - operation_service.py: create (pending), confirm, list_by_user
   - portfolio_service.py: recalculate_positions, get_summary

4. API endpoints (backend/app/api/):
   - GET  /api/v1/users/me
   - POST /api/v1/accounts
   - GET  /api/v1/accounts
   - POST /api/v1/assets
   - GET  /api/v1/assets
   - POST /api/v1/operations
   - GET  /api/v1/operations
   - PATCH /api/v1/operations/{id}/confirm
   - GET  /api/v1/portfolio/summary
   - GET  /api/v1/portfolio/positions

5. Portfolio Engine rules:
   - buy: quantity += q, average_price = weighted average
   - sell: quantity -= q
   - deposit/withdraw: no position change
   - dividend/coupon/fee/tax: no position change
   - manual_valuation: update average_price only
   - recalculate_positions triggered after every confirm

6. New Alembic migration:
   - add telegram_user_id (nullable) to users table

7. Update requirements.txt:
   - python-jose[cryptography]
   - passlib[bcrypt]

Important:
Write working code, not pseudocode.
Keep service layer thin — no over-engineering.
After finishing, show changed files and next recommended stage.
```

---

## Stage 3 — Web Dashboard
*(добавить после завершения Stage 2)*

---

## Stage 4 — AI Command Bar
*(добавить после завершения Stage 3)*
