# GenBI Module

← [[00_Project_Index]] | [[04_Roadmap]]

**Stage:** 5
**Статус:** 🔲 Запланирован

## Принцип
GenBI не изобретает числа. AI конвертирует вопрос в `analytics spec`. Backend считает из БД. Frontend рендерит.

```
User question
    ↓
AI → AnalyticsSpec (JSON)
    ↓
Analytics Engine → данные из PostgreSQL
    ↓
Frontend → визуализация
```

## AnalyticsSpec (черновик)
```json
{
  "intent": "portfolio_value_over_time",
  "params": {
    "account_id": null,
    "period": "1y",
    "granularity": "month"
  },
  "visualization": "line_chart"
}
```

## Поддерживаемые intents

| Intent | Визуализация |
|---|---|
| `portfolio_value_over_time` | line chart |
| `allocation_by_asset_type` | donut chart |
| `allocation_by_account` | donut chart |
| `top_assets_by_pnl` | bar chart |
| `dividends_over_time` | bar chart |
| `monthly_cashflow` | bar chart |
| `asset_performance` | line chart |

## Поддерживаемые визуализации
- `line_chart`
- `bar_chart`
- `donut_chart`
- `kpi_cards`
- `table`

## Открытые вопросы
- Как хранить исторические цены для `portfolio_value_over_time`? → [[10_Open_Questions]]
- Нужен ли кэш для дорогих аналитических запросов?
