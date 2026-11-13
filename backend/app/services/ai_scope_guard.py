"""
AI Scope Guard — rule-based classifier for AI request scope enforcement.

Classifies user text as:
  ALLOWED             — clearly within service scope (finance / portfolio / service nav)
  BLOCKED             — injection attempt, out-of-scope, investment advice, or illegal request
  NEEDS_CLARIFICATION — ambiguous; caller may proceed with a scope-reminder prompt

Call before any AI provider invocation. If BLOCKED, return safe_response directly
and skip the AI provider entirely.

This guard is a defense-in-depth layer, not the only protection:
  - Backend validates all data before persisting (independent of AI output)
  - AI only produces drafts; user confirmation is always required
  - Route layer enforces auth / ownership independently
"""

import re
from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class ScopeCategory(Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    NEEDS_CLARIFICATION = "needs_clarification"


@dataclass(frozen=True)
class ScopeResult:
    category: ScopeCategory
    reason: str
    safe_response: str | None = None


SAFE_RESPONSE = (
    "Я отвечаю только по вашему финансовому учёту, "
    "портфелю, операциям и функциям сервиса."
)


# ---------------------------------------------------------------------------
# Block rule groups  (ordered: most severe first)
# ---------------------------------------------------------------------------

def _re(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


# Prompt injection / jailbreak
# Patterns use .{0,50}? so extra words between trigger and target don't bypass detection.
_INJECTION: list[re.Pattern] = [
    # "ignore [all/previous/your/any] [previous] instructions" — handles multi-word variants
    _re(r"ignore\s+(?:\w+\s+){0,3}(?:instructions?|rules?|prompt|constraints?)"),
    _re(r"forget\s+(?:\w+\s+){0,3}(?:rules?|instructions?|constraints?)"),
    _re(r"\b(jailbreak|dan\s+mode|developer\s+mode|god\s+mode)\b"),
    _re(r"(act|behave)\s+as\s+(if|though)\s+(you\s+)?(have|had|are|were)\s+(no\b|without)"),
    _re(r"pretend\s+(you\s+)?(have|had|are|were)\s+(no\b|without)"),
    _re(r"bypass\s+(your\s+)?(safety|filter|restriction|rule|guardrail|scope)"),
    _re(r"(disable|remove|override|turn\s+off)\s+(your\s+)?(restriction|filter|rule|safety|guard|scope)"),
    # Generic: "new instructions", "your real instructions", etc.
    _re(r"\b(new|real|true|actual|original|secret)\s+(instructions?|rules?|prompt|persona)\b"),
    _re(r"\byou\s+(are\s+now|will\s+now|must\s+now|should\s+now)\s+(act|behave|respond|answer|play)\b"),
    # Russian
    _re(r"игнорируй\s+(?:\w+\s+){0,3}(?:инструкции|правила|ограничения)"),
    _re(r"забудь\s+(?:\w+\s+){0,3}(?:правила|инструкции|ограничения)"),
    _re(r"(обойди|отключи|сними)\s+(ограничения|правила|фильтр|рамки)"),
    _re(r"притворись\s+.{0,40}?(без\s+ограничений|свободн)"),
]

# System prompt disclosure
_SYSTEM_PROMPT: list[re.Pattern] = [
    _re(r"(show|reveal|print|display|tell\s+me|what\s+is|what\s+are)\s+(your\s+)?(system\s*prompt|initial\s+prompt)"),
    _re(r"(repeat|output|write\s+out)\s+(your\s+)?(system|initial|original|first)\s+(prompt|instructions?|message)"),
    _re(r"what\s+(instructions?|rules?|prompt)\s+(were\s+you|are\s+you|have\s+you\s+been)\s+(given|told|instructed)"),
    # Russian
    _re(r"(покажи|раскрой|выведи)\s+(свой\s+)?системн(ый\s+промпт|ые\s+инструкции)"),
    _re(r"(какие|какой)\s+(у\s+тебя|твои)\s+(инструкции|системный\s+промпт)"),
]

# Investment advice — "what/which to buy" (not "I bought")
_INVESTMENT_ADVICE: list[re.Pattern] = [
    _re(r"what\s+(should|can|do)\s+i\s+(buy|invest\s+in|purchase)"),
    # Use \bstocks?\b so "stocks" (plural) also matches
    _re(r"(recommend|advise|suggest)\s+.{0,40}\b(stocks?|bonds?|etf|funds?|investments?|crypto)\b.{0,20}\b(buy|invest|purchase|get)\b"),
    _re(r"(best|top|good|which)\s+\b(stocks?|bonds?|etf|funds?|investments?)\b\s+(to\s+)?(buy|invest|purchase|get|own)"),
    _re(r"(give\s+me\s+)?(investment\s+advice|financial\s+advice|trading\s+advice|trading\s+tip)"),
    _re(r"where\s+(should\s+i\s+)?invest\s+my\s+(money|savings|capital)"),
    # Russian — "что/куда купить/вложить" as advice (not past-tense recording)
    # Fix: optional group uses ((?:word)\s+)? so trailing space is always consumed
    _re(r"(куда|во\s+что)\s+((?:лучше|можно|стоит)\s+)?(вложить|инвестировать)"),
    _re(r"что\s+((?:лучше|стоит)\s+)?(купить|вложить|инвестировать)\s*(сейчас|сегодня)?"),
    _re(r"(посоветуй|порекомендуй)\s+(что|куда|какие?|какой)\s+.{0,40}(купить|вложить|инвестировать)"),
    _re(r"(какие?|какой)\s+(акции|облигации|фонды?|активы?)\s+(лучше|стоит|выгоднее?|купить|вложить)"),
    _re(r"инвестиционн(ый|ые|ого)\s+(совет|рекомендаци)"),
]

# Illegal / harmful
_ILLEGAL: list[re.Pattern] = [
    _re(r"(evade|avoid|hide|cheat\s+on)\s+(taxes?|tax\s+payment)"),
    _re(r"\btax\s+evasion\b"),
    _re(r"(money\s+laundering|launder\s+money)"),
    # Russian
    _re(r"уклонени[ея]\s+от\s+налог"),
    _re(r"отмывани[ея]\s+(денег|средств|капитала)"),
    _re(r"(скрыть|скрывать|спрятать)\s+(доход|деньги|средства)\s+от\s+(налог|государств)"),
]

# Ordered list: each entry is (patterns, reason_tag)
_BLOCK_RULES: list[tuple[list[re.Pattern], str]] = [
    (_INJECTION, "prompt_injection"),
    (_SYSTEM_PROMPT, "system_prompt_request"),
    (_INVESTMENT_ADVICE, "investment_advice"),
    (_ILLEGAL, "illegal_request"),
]


# ---------------------------------------------------------------------------
# Allow keywords — finance / service scope signal
# ---------------------------------------------------------------------------

# English words use full word boundaries (\bword\b).
# Russian stems use only a leading word boundary (\bstem) — no trailing \b —
# so that inflected forms (дивидендЫ, доходЫ, процентЫ, etc.) still match.
_FINANCE_SIGNAL = re.compile(
    r"(?:"
    # English — full boundaries
    r"\b(?:buy|sell|bought|sold|purchase|deposit|withdraw|withdrawal"
    r"|dividend|coupon|fee|commission|portfolio|position|balance"
    r"|profit|loss|pnl|account|broker|savings|asset|stock|bond"
    r"|etf|fund|ticker|crypto|income|expense|salary|interest|rate"
    r"|operation|dashboard|report|add|create|delete|show|find"
    r"|open|configure|settings)\b"
    r"|"
    # Russian stems — leading boundary only (allows all case/declension forms)
    r"\b(?:купил|продал|куп(?:ить|аю)|прода(?:ть|ю)"
    r"|пополн|вывод|вывест|вывел"
    r"|дивиденд|купон|комисси|вознаграждени"
    r"|переоцени|переоценить|переоценк"
    r"|портфел|позици|баланс|прибыл|убыток|доходност|остаток"
    r"|доход|расход|зарплат|денежн|деньг|потрат|трат|кредит|ипотек"
    r"|счет|счёт|вклад|накопительн|брокер"
    r"|актив|акци|облигаци|фонд|тикер"
    r"|процент|ставк|начислени"
    r"|налог|ндфл|руб"
    r"|операци|отч[её]т"
    r"|добавить|создать|удалить|показать|найти|открыть|настройк"
    r")"
    r")",
    re.IGNORECASE | re.UNICODE,
)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def classify(text: str) -> ScopeResult:
    """
    Classify a user query for AI scope enforcement.

    1. Run block rules (injection, system prompt, investment advice, illegal).
       First match wins → BLOCKED.
    2. Check for finance / service keywords → ALLOWED.
    3. Default → BLOCKED (out_of_scope).
    """
    if not text or not text.strip():
        return ScopeResult(
            category=ScopeCategory.BLOCKED,
            reason="empty_input",
            safe_response=SAFE_RESPONSE,
        )

    # ── 1. Blocked checks ────────────────────────────────────────────────────
    for patterns, reason in _BLOCK_RULES:
        for pattern in patterns:
            if pattern.search(text):
                return ScopeResult(
                    category=ScopeCategory.BLOCKED,
                    reason=reason,
                    safe_response=SAFE_RESPONSE,
                )

    # ── 2. Finance / service signal ──────────────────────────────────────────
    if _FINANCE_SIGNAL.search(text):
        return ScopeResult(category=ScopeCategory.ALLOWED, reason="finance_scope")

    # ── 3. Out of scope ──────────────────────────────────────────────────────
    return ScopeResult(
        category=ScopeCategory.BLOCKED,
        reason="out_of_scope",
        safe_response=SAFE_RESPONSE,
    )
