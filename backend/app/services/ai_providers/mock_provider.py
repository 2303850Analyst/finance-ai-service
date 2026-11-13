"""
Mock AI provider that parses Russian-language finance operation descriptions.
Uses rule-based regex — no external API required.
"""
import re

from app.services.ai_providers.base import RawProposal

# ── constants ─────────────────────────────────────────────────────────────────

_NUM = r"(\d+(?:[.,]\d+)?)"

# Russian name fragments → canonical ticker
_NAME_TICKER: dict[str, str] = {
    "сбер": "SBER",
    "сбера": "SBER",
    "сбербанк": "SBER",
    "сбербанка": "SBER",
    "яндекс": "YDEX",
    "яндекса": "YDEX",
    "лукойл": "LKOH",
    "лукойла": "LKOH",
    "лукойле": "LKOH",
    "биткоин": "BTC",
    "биткоина": "BTC",
    "биток": "BTC",
    "bitcoin": "BTC",
}

# Tickers that represent currencies — do not treat as asset tickers
_CURRENCY_TICKERS = {"RUB", "USD", "EUR", "GBP", "CNY", "JPY", "USDT"}

# Phrases that clearly signal a query/report request, not an operation
_NOT_OP_RE = re.compile(
    r"^\s*(?:покажи|показать|посмотри|посмотреть|что\s+у|как\s+|"
    r"отчет|анализ|расскажи|история|сводка|помоги|объясни)",
    re.IGNORECASE,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _n(s: str) -> str:
    """Normalise decimal separator to dot."""
    return s.replace(",", ".")


def _find_price_after_po(text: str) -> str | None:
    """Extract the number immediately after the word 'по' (price marker)."""
    m = re.search(r"\bпо\s+" + _NUM, text, re.IGNORECASE)
    # Make sure the word after 'по' is numeric, not 'счету'
    if m:
        return _n(m.group(1))
    return None


def _find_qty_and_price(text: str) -> tuple[str | None, str | None]:
    """For buy/sell: qty is the first number (before 'по'), price is after 'по'."""
    price = _find_price_after_po(text)
    # Restrict qty search to the part before 'по'
    po_idx = text.lower().find(" по ")
    search_zone = text[:po_idx] if po_idx >= 0 else text
    m = re.search(_NUM, search_zone)
    qty = _n(m.group(1)) if m else None
    return qty, price


def _find_fee_amount(text: str) -> str | None:
    """Extract the number right after 'комиссия/комиссию/комиссии'."""
    m = re.search(r"комисси[яию]\s+" + _NUM, text, re.IGNORECASE)
    return _n(m.group(1)) if m else None


def _find_rub_amount(text: str) -> str | None:
    """Extract NUMBER before 'рублей / руб / ₽'."""
    m = re.search(_NUM + r"\s*(?:рублей|рубля|руб\.?|₽)", text, re.IGNORECASE)
    return _n(m.group(1)) if m else None


def _find_account(text: str) -> str | None:
    """Extract account name after 'счет / счету / по счету'."""
    m = re.search(
        r"(?:по\s+)?счет[уаюе]?\s+([^\s,][^,]*?)(?:\s*,|\s*$)",
        text,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _find_ticker(text: str) -> str | None:
    """Find a Latin uppercase ticker word (2–5 chars), skipping currency symbols."""
    for m in re.finditer(r"\b([A-Z]{2,5})\b", text):
        t = m.group(1)
        if t not in _CURRENCY_TICKERS:
            return t
    return None


def _find_asset_ticker(text: str) -> str | None:
    """Return ticker from explicit uppercase word or known Russian name."""
    t = _find_ticker(text)
    if t:
        return t
    tl = text.lower()
    for name, ticker in _NAME_TICKER.items():
        if re.search(r"\b" + re.escape(name) + r"\b", tl):
            return ticker
    return None


# ── provider ──────────────────────────────────────────────────────────────────


class MockProvider:
    async def parse_operation(self, text: str) -> RawProposal:
        if _NOT_OP_RE.match(text):
            return RawProposal(
                is_operation=False,
                message=(
                    "Это не финансовая операция. "
                    "Попробуйте: «Купил 10 акций SBER по 280»."
                ),
            )

        tl = text.lower()

        is_buy = bool(re.search(r"\b(?:купил[аи]?|приобрел[аи]?)\b", tl))
        is_sell = bool(re.search(r"\bпродал[аи]?\b", tl))
        is_div = bool(re.search(r"\bдивиденд", tl))
        # fee is standalone only when not part of a buy/sell sentence
        is_fee = bool(re.search(r"\bкомисси", tl)) and not is_buy and not is_sell
        is_manual_val = bool(re.search(r"\bпереоцен", tl))

        if not any([is_buy, is_sell, is_div, is_fee, is_manual_val]):
            return RawProposal(
                is_operation=False,
                message="Не удалось распознать тип операции.",
            )

        account_name = _find_account(text)

        # ── buy / sell ────────────────────────────────────────────────────────
        if is_buy or is_sell:
            op_type = "buy" if is_buy else "sell"
            qty, price = _find_qty_and_price(text)
            asset_ticker = _find_asset_ticker(text)
            fee = _find_fee_amount(text)

            missing: list[str] = []
            if qty is None:
                missing.append("quantity")
            if price is None:
                missing.append("price")

            return RawProposal(
                is_operation=True,
                operation_type=op_type,
                asset_ticker=asset_ticker,
                account_name=account_name,
                quantity=qty,
                price=price,
                fee=fee,
                currency="RUB",
                clarification_needed=bool(missing),
                missing_fields=missing,
            )

        # ── dividend ──────────────────────────────────────────────────────────
        if is_div:
            amount = _find_rub_amount(text)
            asset_ticker = _find_asset_ticker(text)
            return RawProposal(
                is_operation=True,
                operation_type="dividend",
                asset_ticker=asset_ticker,
                account_name=account_name,
                amount=amount,
                currency="RUB",
            )

        # ── standalone fee ────────────────────────────────────────────────────
        if is_fee:
            amount = _find_fee_amount(text) or _find_rub_amount(text)
            return RawProposal(
                is_operation=True,
                operation_type="fee",
                account_name=account_name,
                amount=amount,
                currency="RUB",
            )

        # ── manual valuation ──────────────────────────────────────────────────
        if is_manual_val:
            asset_ticker = _find_asset_ticker(text)
            price = _find_price_after_po(text)
            return RawProposal(
                is_operation=True,
                operation_type="manual_valuation",
                asset_ticker=asset_ticker,
                account_name=account_name,
                price=price,
                currency="RUB",
            )

        return RawProposal(is_operation=False, message="Не удалось распознать операцию.")
