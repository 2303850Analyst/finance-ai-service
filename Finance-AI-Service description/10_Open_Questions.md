# Open Questions

← [[00_Project_Index]]

## Архитектурные

- [ ] Как хранить исторические цены активов?
  - Отдельная таблица `price_history(asset_id, date, close_price)`?
  - Или только последняя цена в `assets.last_price`?
  - Нужно для GenBI `portfolio_value_over_time` → [[07_GenBI_Module]]

- [ ] Пересчитывать `positions` синхронно или через фоновую задачу (Celery/ARQ)?
  - Синхронно проще, но может быть медленно при большом числе операций

- [ ] Нужен ли кэш для аналитических запросов GenBI?
  - Redis? Или кэш на уровне PostgreSQL materialized views?

## Auth / Security

- [ ] Срок жизни JWT: access token 15 мин + refresh token 7 дней?
- [ ] Rate limiting на AI endpoints?

## Telegram

- [ ] Как привязать Telegram user к существующему web-аккаунту?
  - OTP через web-интерфейс?
  - Уникальный `/link <код>` команда?
- [ ] Webhook или long polling?
  - Webhook требует публичного URL (ngrok для dev)

## AI Parser

- [ ] Что делать с неизвестными тикерами?
  - Предлагать создать новый Asset?
  - Поиск по имени?
- [ ] Как тестировать MockProvider?
  - Фиксированные ответы на конкретные тексты?

## Import & Market Data (Stage 7)

- [ ] Какие брокеры поддерживать первыми? (Тинькофф, Сбербанк, ВТБ?)
- [ ] Источник рыночных данных: MOEX API, Yahoo Finance, другое?

## Финансовые правила (зафиксировано)

### Терминология процентов
- **Расчётная база**: ежедневный остаток (всегда, не настраивается)
- **Период выплаты** (`payout_frequency`): `daily` / `monthly` / `at_maturity` — когда проценты зачисляются
- UI должен показывать именно период выплаты как ключевой параметр, а расчётную базу как вспомогательную подсказку
- `InterestModal` и `CreateDepositModal` теперь оба отображают динамически: "Период выплаты: Ежемесячно"

### Правила удаления сущностей
- Аккаунт: DELETE блокируется (409) если есть операции. Backend: `DELETE /accounts/{id}`
- Актив: DELETE блокируется (409) если используется в операциях или позициях
- Вклад: это аккаунт типа `deposit`; Delete блокируется если есть операции (т.е. есть principal)
- "Закрыть вклад" ≠ "Удалить вклад". Закрыть = перевод principal на другой счёт.

### Transfer
- Transfer — не доход, не расход. Total capital = −fee только.
- `from_account -= (amount + fee)`, `to_account += amount`
- В New Operation форме `transfer` недоступен → только через кнопку "Перевод" на Dashboard
- В Operations filter — transfer отображается с меткой "Перевод"

### НДФЛ
- НДФЛ = 13% от прибыли, не от суммы продажи
- Прибыль = proceeds − FIFO себестоимость − sell_fee
- Если FIFO история неполная → default 0 + amber warning: "Введите сумму вручную"
- Tax операция создаётся только после явного подтверждения пользователя

### Deposit close (MVP)
- Переводится только основная сумма (principal), не accrued_interest
- Accrued_interest — производная, не материализованная сумма
- Если банк выплатил проценты → отдельная операция "Ввести доход" с income_source=interest

### Total capital vs Budget
- **Total Capital** = cash_balances + investment_positions (по себестоимости)
- **Budget / Денежный поток** = income − expenses за период (flow)
- Это разные метрики. Dashboard показывает обе раздельно.

### Текущие ограничения (TODO)
- Обязательства (liabilities) не моделируются — кредитные платежи уменьшают cash без создания liability
- Рыночные цены не используются — portfolio value по себестоимости
- Только RUB — мультивалютность не реализована
- Нет реального AI провайдера (MockProvider)
- Нет GenBI
- Нет FX-конвертации
- Нет Telegram интеграции

## Решённые вопросы
- ✅ Enum handling: DO block + `postgresql.ENUM(create_type=False)` → [[03_ADR#ADR-004]]
- ✅ Async Alembic: `asyncio.run` в `env.py` → [[05_Stage_1_Foundation]]
- ✅ Transfer: не доход/расход, validation source cash, FIFO queue, budget exclusion
- ✅ Interest UI: reactive payout_frequency label в InterestModal и CreateDepositModal
- ✅ NDFL: FIFO cost basis, не 13% от proceeds
- ✅ Deposit close: principal only, не principal + accrued_interest
- ✅ Delete guards: account, asset, deposit — все заблокированы если есть financial history (182 тестов)
