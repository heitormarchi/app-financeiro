"""
Phase C: LLM insight generation via OpenRouter (free tier).
Receives pre-enriched transactions and produces natural language insights.
"""
from openai import AsyncOpenAI

from app.core.config import settings
from app.models.models import Transaction

client = AsyncOpenAI(
    api_key=settings.openrouter_key,
    base_url="https://openrouter.ai/api/v1",
)

OPENROUTER_MODEL = "google/gemma-3-27b-it"

SYSTEM_PROMPT = """Você é um consultor financeiro pessoal direto e empático, falando com um brasileiro sobre suas finanças.

Seu objetivo: transformar dados de transações em um insight proativo e acionável em linguagem natural.

Regras:
- Fale como um amigo que entende de finanças, não como um robô
- Seja específico com valores e percentuais
- Aponte padrões sem julgamento
- Sugira uma ação concreta quando relevante
- Máximo 3 frases
- Use o contexto temporal (dia da semana, horário) quando disponível"""


def _summarize_transactions(transactions: list[Transaction]) -> str:
    lines = []
    for t in transactions:
        merchant = t.merchant or t.raw_description[:30]
        category = f"{t.category}/{t.subcategory}" if t.subcategory else t.category or "?"
        lines.append(f"- {t.date.strftime('%d/%m %Hh')} | {merchant} | R${abs(float(t.amount)):.2f} | {category}")
    return "\n".join(lines)


async def generate_daily_insight(transactions: list[Transaction], period_days: int = 30) -> str:
    """Generate a proactive daily insight from a list of enriched transactions."""
    if not transactions:
        return "Nenhuma transação encontrada para o período."

    summary = _summarize_transactions(transactions)
    total_spend = sum(abs(float(t.amount)) for t in transactions if float(t.amount) < 0)

    user_prompt = f"""Analise as transações dos últimos {period_days} dias e gere um insight proativo:

Gasto total: R${total_spend:.2f}
Transações:
{summary}

Gere um insight útil e acionável sobre o padrão financeiro do usuário."""

    response = await client.chat.completions.create(
        model=OPENROUTER_MODEL,
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.choices[0].message.content
