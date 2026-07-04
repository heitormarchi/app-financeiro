# Purpose & context
Heitor is a solo technical founder building a B2C personal finance mobile app for the Brazilian market, with the goal of generating monthly recurring revenue via a Freemium model. The core differentiator: eliminating user effort entirely — no manual transaction entry, no discipline required — replaced by proactive AI insights delivered in plain language without the user needing to ask. Competitors (Mobills, Organizze, Guiabolso, Minhas Economias) are framed as "cofres, não conselheiros" (vaults, not advisors); the app aims to be an active financial advisor.
Heitor is himself the target user — having tried multiple apps and spreadsheet approaches without lasting success — making the pain point personally validated. The root cause identified: existing apps demand manual discipline instead of eliminating the need for it.
User acquisition strategy: sponsored Instagram campaigns. Claude is acting as the primary developer on the project.

# Current state
The project is in pre-build / architecture phase with the following fully defined:

MVP feature set: Cadastro/Login, Open Finance connection, dashboard with summary, proactive daily AI insights, conversational chat, push alerts
User journey (4 stages): Descoberta (Instagram/referral) → Onboarding (signup + Open Finance connection + first insight = "uau" moment) → Uso diário (proactive notification, direct app, or WhatsApp) → Valor entregue (effortless understanding → engagement → paid conversion). Critical bottleneck: onboarding through the first insight
Transaction enrichment architecture (5 layers):

- Raw ingestion via Pluggy/Belvo (OAuth 2.0, sync every 6h)
- Regex dictionary base (~60% coverage)
- Temporal/routine inference — learns work schedule in ~2 weeks, resolves ambiguities like Uber (work commute vs. leisure) (+15%)
- Anonymous collective intelligence — aggregate patterns from other users (+10%)
- LLM (Claude) generates insight in natural language → cumulative accuracy: 60→75→85→95%+


Cost structure: Pluggy is the dominant cost driver at scale; infrastructure and AI API costs are marginal. Strategies to reduce early costs: negotiate a startup-friendly Pluggy plan, use Claude Haiku for routine insights / Sonnet for on-demand chat, leverage prompt caching, maximize Supabase free tier


# Current build status

Phase A (skeleton backend) — CONCLUÍDO (2026-04-28)
- FastAPI + SQLAlchemy 2.0 async + Pydantic v2 em `backend/`
- 5 tabelas criadas: users, bank_connections, transactions, user_routines, collective_patterns
- Camadas 1-3 do enriquecimento implementadas em `backend/app/services/enrichment_service.py`
- Cliente Pluggy em `backend/app/services/pluggy_service.py`
- Geração de insight com Claude Haiku em `backend/app/services/insight_service.py`
- Próximo passo: criar `.env` com credenciais reais e iniciar Phase B (Pluggy integration)

Phase B — Pluggy integration (pendente credenciais: Pluggy + Supabase)
Phase C — AI insight generation (placeholder implementado, precisa de dados reais)

# Decisões de produto (2026-04-28)

**Freemium split:**
- Free: 1 banco via Open Finance + 1 importação via OFX
- Pago: conexões ilimitadas (Open Finance + OFX)
- Diferenciador: quantidade de fontes de dados, não features. Mesma qualidade de insight para todos.

**Disparo de insight/notificação:**
- Threshold-based, não horário fixo
- Dispara quando: categoria ultrapassa 20% da média dos 30 dias anteriores; 2 dias sem transação e nova aparece; domingo às 18h (resumo semanal)
- Máximo 1 notificação/dia; silêncio se nada relevante

**Experiência do dia 1 (pouco histórico):**
- Estado "aprendendo padrões" com progresso visual
- OFX/CSV como atalho para importar histórico imediatamente
- Importação via OFX apenas (formato padronizado, cobre todos os bancos BR)
- CSV fora do escopo sem previsão

# On the horizon

Next product phase: WhatsApp integration + financial goals feature
Instagram-based user acquisition campaigns
Validar fluxo de consentimento Pluggy com usuário real (maior risco não testado)


# Key learnings & principles

The primary abandonment driver in existing finance apps is manual data entry — eliminating it is the core value proposition, not just a feature
Temporal inference (learning user routine over ~2 weeks) is a proprietary insight layer that resolves categorical ambiguity at scale without user input
Anonymous cross-user pattern matching compounds enrichment accuracy meaningfully beyond what individual-user data alone can achieve
Pluggy dominates cost structure early; managing this via negotiation and tiered AI model usage is critical for unit economics at beta/MVP stage
Onboarding to first insight is the highest-leverage moment in the user journey — this is where the product must prove its value


# Approach & patterns

Heitor contributes product and architectural ideas; Claude executes as primary developer
Architecture is designed in layers with cumulative accuracy targets — pragmatic, measurable approach to a hard data quality problem
Cost analysis is structured by growth phase (beta → MVP launch → traction) to inform decisions at each stage
Conversations are conducted in Brazilian Portuguese with domain-specific fintech terminology


# Tools & resources

| Layer | Technology |
|---|---|
| Mobile | Expo + React Native |
| Backend API | FastAPI (Python 3.11+) |
| Database | PostgreSQL próprio na VPS |
| ORM | SQLAlchemy 2.0 async |
| Validation | Pydantic v2 |
| Auth | Supabase Auth (só o serviço de auth, DB é próprio) |
| Open Finance | Pluggy SDK |
| Importação histórico | OFX parser |
| AI | Anthropic SDK (Claude Haiku para insights rotina / Sonnet para chat) |
| Scheduled jobs | Trigger.dev |
| Deploy | VPS própria (backend + PostgreSQL) |
| Push notifications | Expo Push |

Heitor has Python knowledge. Open Finance regulatory context: Banco Central do Brasil framework (4 implementation phases).