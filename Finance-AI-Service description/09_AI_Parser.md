# AI Operation Parser

← [[00_Project_Index]] | [[04_Roadmap]]

**Stage:** 4
**Статус:** 🔲 Запланирован

## Задача
Принять свободный текст от пользователя → вернуть структурированное предложение операции.

```
"купил 10 акций Сбера по 280"
    ↓
{
  "operation_type": "buy",
  "asset_ticker": "SBER",
  "quantity": 10,
  "price": 280,
  "currency": "RUB",
  "confidence": 0.95
}
```

## Provider Abstraction
```python
class AIProvider(Protocol):
    async def parse_operation(self, text: str, context: UserContext) -> OperationProposal: ...

class MockProvider:      # для разработки и тестов
class OpenAIProvider:    # production
```

## Флоу
```
User input (text)
    ↓
AIProvider.parse_operation()
    ↓
OperationProposal (pending, не в БД)
    ↓
Frontend показывает: «Вы имели в виду...?»
    ↓
User подтверждает → POST /operations (status=pending)
    ↓
PATCH /operations/{id}/confirm → confirmed
    ↓
Audit log записывает AI-предложение
```

## Правила
- AI **никогда** не пишет в БД напрямую → [[03_ADR#ADR-002]]
- Каждое AI-предложение логируется в `audit_logs`
- `confidence < 0.7` → показывать предупреждение

## Открытые вопросы
→ [[10_Open_Questions]]
- Как обрабатывать неизвестные тикеры?
- Нужен ли retry при низком confidence?

## Обновление 2026-05-08 — следующий этап реализации

Stage 3 завершён. Stage 4 — следующий.

### Принципы реализации

- **Provider abstraction**: `AIProvider(Protocol)` — единый интерфейс. `MockProvider` для разработки и тестов (детерминированные ответы без LLM), `OpenAICompatibleProvider` для production (любой OpenAI-совместимый endpoint).
- **AI не пишет в БД напрямую**: `parse_operation()` возвращает `OperationProposal` — черновик, не сохранённый объект. Запись происходит только после явного подтверждения пользователем.
- **Backend валидирует proposal**: перед подтверждением backend проверяет `asset_id`, `account_id`, `quantity`, `price` — те же правила, что и для обычного `OperationCreate`.
- **Frontend флоу**: текстовое поле → отправка → превью предложенной операции (тип, тикер, количество, цена, сумма) → кнопки «Подтвердить» / «Отменить» → при подтверждении `POST /operations`.
- **Audit log**: каждое AI-предложение логируется в `audit_logs` (исходный текст, proposal JSON, confidence, был ли подтверждён).
