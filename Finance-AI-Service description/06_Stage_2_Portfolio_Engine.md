# Stage 2 — Portfolio Engine

← [[04_Roadmap]]

**Статус:** ✅ Готов к commit
**Tests:** 14 passed
**Commit status:** ready to commit
**Промпт для реализации:** [[11_Prompts_For_Claude_Code]]

## Цель
Добавить auth, CRUD для основных сущностей и базовый portfolio engine.
После Stage 2 пользователь может зарегистрироваться, ввести операции и видеть позиции.

## Что нужно реализовать

### Auth
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login` → JWT
- Dependency `get_current_user`
- `passlib[bcrypt]` для хэширования паролей
- `python-jose` для JWT

### Pydantic Schemas
```
schemas/
├── user.py       # UserCreate, UserOut
├── account.py    # AccountCreate, AccountOut
├── asset.py      # AssetCreate, AssetOut
├── operation.py  # OperationCreate, OperationOut
└── position.py   # PositionOut
```

### CRUD Endpoints

| Method | Path | Описание |
|---|---|---|
| GET | `/api/v1/users/me` | Профиль |
| POST | `/api/v1/accounts` | Создать счёт |
| GET | `/api/v1/accounts` | Список счетов |
| POST | `/api/v1/assets` | Создать актив |
| GET | `/api/v1/assets` | Список активов |
| POST | `/api/v1/operations` | Создать операцию |
| GET | `/api/v1/operations` | Список операций |
| PATCH | `/api/v1/operations/{id}/confirm` | Подтвердить операцию |

### Portfolio Engine
```
services/portfolio.py
├── recalculate_positions(account_id) → List[Position]
├── get_portfolio_summary(user_id) → PortfolioSummary
└── trigger: вызывается после confirm операции
```

### API
- `GET /api/v1/portfolio/summary` — общая стоимость, позиции
- `GET /api/v1/portfolio/positions` — список позиций

## Зависимости к добавлению
```
python-jose[cryptography]
passlib[bcrypt]
```

## Критерий готовности
- Можно зарегистрироваться и войти
- Можно создать счёт, актив, операцию
- После confirm операции — positions обновляются
- `/portfolio/summary` возвращает корректные данные

---

## Итог Stage 2

- Backend получил рабочие CRUD endpoints для accounts, assets, operations.
- Portfolio engine пересчитывает positions из confirmed operations — полностью, с нуля при каждом изменении.
- История операций является единственным источником правды (positions — только кэш).
- Seed dev data работает идемпотентно: можно вызывать многократно без побочных эффектов.
- Тестовая инфраструктура стабилизирована через отдельную БД `finance_ai_test`.

## Уроки

- Async SQLAlchemy тесты требуют аккуратного управления event loop: engine и session должны создаваться в том же loop, в котором используются.
- Function-scoped async engine/session безопаснее module/session-scoped для текущего MVP — нет риска утечки состояния между тестами.
- PostgreSQL enum и Alembic требуют явного контроля: DO-блоки для создания, `postgresql.ENUM(create_type=False)` для колонок.
- `amount` нельзя доверять клиенту для `buy`/`sell` — лучше вычислять на backend из `quantity * price`.
