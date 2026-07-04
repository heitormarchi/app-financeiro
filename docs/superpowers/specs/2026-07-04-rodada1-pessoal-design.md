# Rodada 1 — Uso pessoal: OFX + SMS + NFC-e + PWA

**Data:** 2026-07-04
**Status:** Aprovado pelo Heitor (design validado em sessão)
**Escopo:** design da rodada 1 (uso pessoal). Sem desenvolvimento nesta fase.

## 1. Contexto e objetivo

O app-financeiro tinha arquitetura voltada a B2C via Pluggy (agregador Open Finance). Esta rodada reposiciona o projeto: **primeiro resolver a organização financeira pessoal do Heitor**, com custo zero e sem intermediários, mantendo o caminho aberto para a fase SaaS (mercado brasileiro, Freemium).

**Critério de sucesso da rodada 1:** Heitor sabe onde gasta — dashboard por categoria consultável a qualquer momento + resumo semanal por push, sem lançamento manual de transações.

### Por que não Open Finance direto

O Open Finance Brasil é um ecossistema fechado regulado pelo BACEN: só instituições autorizadas e registradas no Diretório de Participantes podem receber dados de clientes (certificados ICP-Brasil, perfil FAPI-BR, compliance). Pessoa física/dev solo não se qualifica. A API de Extratos do BB Developers atende apenas contas PJ do CNPJ dono da aplicação. Decisão: **OFX manual é o único canal direto banco→usuário viável para PF** e é o adotado. Agregadores (Pluggy/Meu Pluggy) ficam como upgrade futuro opcional.

## 2. Decisões desta rodada

| Tema | Decisão |
|---|---|
| Ingestão | OFX manual (BB conta + Caixa conta) + SMS do cartão Caixa via Atalho iOS + NFC-e por QR (SC) |
| Interface | PWA (React SPA via Vite) servida como estáticos pelo FastAPI na VPS |
| Backend existente | Reaproveitar e podar: mantém models/enrichment/insight; aposenta `pluggy_service` e Supabase Auth |
| Auth | Single-user por API key estática (multiusuário volta na fase SaaS) |
| Entrega de valor | Dashboard + resumo semanal via web push (domingo 18h) |
| Scheduler | APScheduler embutido no FastAPI (substitui Trigger.dev) |
| IA | `insight_service` mantido no OpenRouter (modelo atual); troca de provedor é configuração, não arquitetura |

## 3. Arquitetura

```
iPhone (Safari/PWA) ─┐                          ┌─ PostgreSQL (VPS/EasyPanel)
Windows (browser)  ──┼─▶ FastAPI (VPS/EasyPanel)┤
Atalho iOS (SMS)   ──┘    ├ /api/v1/*  (JSON)   └─ APScheduler (in-process)
                          └ /          (React dist/)
```

- Monorepo `C:\PJ\app-financeiro`: `backend/` (FastAPI) + `frontend/` (Vite + React + TypeScript) + `docs/`.
- Um único serviço de deploy: FastAPI serve API e estáticos do build do front. Sem Node no servidor.
- HTTPS terminado pelo EasyPanel (obrigatório para service worker/push e para proteger a API key).

### Autenticação single-user

- `APP_API_KEY` (string longa aleatória) no `.env`.
- PWA: usuário cola a chave uma vez em Config; fica em `localStorage`; enviada em `X-API-Key` em toda chamada.
- Atalho iOS envia o mesmo header. Comparação constant-time no backend.
- `users` continua no schema com `user_id=1` fixo; nenhuma tabela perde `user_id` (preparação SaaS gratuita).

## 4. Ingestão de dados

### 4.1 OFX (BB conta corrente + Caixa conta corrente)

- Página "Importar": upload de um ou mais arquivos `.ofx`.
- Parser: `ofxparse` (Python), tolerante a encoding (`latin-1`/`cp1252` comuns em bancos BR). Linhas rejeitadas são reportadas sem abortar o import.
- **Deduplicação:** chave `(conta, FITID)`; fallback quando FITID ausente/instável: hash de `(data, valor, memo normalizado)`. Exports quinzenais de 60 dias se sobrepõem por design; reimportar nunca duplica.
- Resposta do import: `{novas: N, duplicadas: M, rejeitadas: K}` exibida no PWA.
- Frequência recomendada de exportação: a cada 2 semanas (janela de 60 dias dos bancos dá folga de sobra).

### 4.2 SMS do cartão de crédito Caixa

- Endpoint: `POST /api/v1/ingest/sms` — body `{text: string, received_at: datetime}`, header `X-API-Key`.
- Origem: automação pessoal do app Atalhos (iOS) "Ao receber mensagem" filtrada por remetente/conteúdo CAIXA → ação "Obter conteúdo de URL" (POST). Roda automaticamente, sem confirmação.
- Fluxo no backend: grava payload cru em `raw_events` → parser regex extrai valor, estabelecimento e data → cria transação `source=sms` → passa pelo pipeline de enriquecimento.
- **Requisito de calibração:** o parser será construído sobre ≥3 SMS reais do cartão Caixa fornecidos pelo Heitor como fixtures de teste (anonimizados). Regex versionado e ajustável sem migração.
- Parse falhou → `raw_events.status=failed`, visível como pendência em Config, reprocessável após ajuste do regex. Nenhum SMS se perde.

### 4.3 NFC-e via QR code (Santa Catarina)

- Página "Cupom": câmera no navegador (BarcodeDetector API; fallback jsQR) lê o QR do cupom → envia URL/chave de acesso (44 dígitos) ao backend.
- Backend consulta o portal público da SEFAZ-SC (`sat.sef.sc.gov.br`), parseia o HTML (BeautifulSoup) e extrai: emitente (nome, CNPJ), data, valor total e **itens** (descrição, código, quantidade, unidade, valor unitário, valor total).
- HTML cru vai para `raw_events` (reprocessável se o layout do portal mudar).
- **Conciliação cupom ↔ transação:** procura transação existente com mesma data (±1 dia) e mesmo valor total (±R$ 0,01). Achou → anexa itens (`receipt_items`) à transação (que veio por SMS ou OFX). Não achou → cria transação `source=nfce`. Match ambíguo → desempata por similaridade do nome do estabelecimento; persiste a escolha.
- Parser desenhado como **estratégia por UF**: SC é a primeira implementação; outros estados são novas estratégias, não refatoração.

### 4.4 Regra anti-dupla-contagem (fatura do cartão)

Compras do cartão entram via SMS em tempo real. O pagamento da fatura aparece depois no extrato OFX como débito único (ex.: "PAG FATURA CARTAO"). Regra: débitos identificados como pagamento de fatura recebem `is_invoice_payment=true` e são **excluídos de todas as agregações de gasto** (dashboard, resumo semanal). Identificação por padrão de descrição no extrato Caixa, com fixture real no teste.

## 5. Modelo de dados (delta sobre o schema atual)

| Tabela | Mudança |
|---|---|
| `transactions` | + `source` enum (`ofx`, `sms`, `nfce`); + `external_id` (FITID/chave dedup); + `is_invoice_payment` bool default false |
| `receipt_items` | **nova**: `id`, `transaction_id` FK, `description`, `product_code`, `quantity`, `unit`, `unit_price`, `total_price` |
| `raw_events` | **nova**: `id`, `user_id`, `type` (`sms`, `nfce`), `payload` (texto/HTML cru), `status` (`parsed`, `failed`), `transaction_id` FK nullable, `created_at` |
| `push_subscriptions` | **nova**: `id`, `user_id`, `endpoint`, `keys` (JSON), `created_at` — uma por dispositivo (iPhone, Windows) |
| `bank_connections` | reinterpretada como cadastro das fontes do usuário (BB conta, Caixa conta, Cartão Caixa); sem colunas Pluggy obrigatórias |
| `users`, `user_routines` | mantidas sem mudança |
| `collective_patterns` | mantida no schema, dormente na rodada 1 |

Migração via Alembic (introduzir se ainda não configurado).

## 6. Enriquecimento e IA

- Pipeline existente mantido: dicionário regex → inferência temporal → (coletivo dormente) → LLM para os casos restantes.
- Novas fontes elevam a qualidade de entrada: SMS traz nome limpo do estabelecimento; NFC-e traz itens (categorização no nível de item vira possível para mercado/farmácia).
- **Feedback loop:** correção manual de categoria na lista de transações grava regra no dicionário do usuário — próxima transação do mesmo estabelecimento já vem certa.
- **Resumo semanal:** APScheduler, domingo 18h (America/Sao_Paulo). Agrega a semana, compara com médias de 30/90 dias, `insight_service` gera 3–4 frases em PT-BR (específicas, com números, uma sugestão acionável). Enviado por web push a todas as `push_subscriptions`; também persistido e exibido no Dashboard (push é canal de entrega, não o registro).
- Web push: `pywebpush` + chaves VAPID no `.env`. iPhone requer PWA instalada na home screen (iOS 16.4+); Windows funciona no navegador.

## 7. PWA — telas

1. **Dashboard** — gasto do mês por categoria (donut), evolução mês a mês (barras), top 5 gastos, comparativo vs. mês anterior, último resumo semanal.
2. **Transações** — lista com filtros (mês, categoria, fonte), edição de categoria inline (alimenta o feedback loop), expansão para itens de cupom.
3. **Importar** — upload OFX, resultado do dedup, histórico de imports.
4. **Cupom** — câmera + leitura de QR, histórico dos últimos cupons escaneados e status da conciliação.
5. **Config** — ativar push neste dispositivo, API key, pendências de parse (`raw_events` com falha) com ação de reprocessar.

Gráficos: Recharts. PWA: manifest + service worker (push e cache de estáticos).

## 8. Tratamento de erros

| Falha | Comportamento |
|---|---|
| SMS não parseia | `raw_events.status=failed`, pendência visível em Config, reprocesso após ajuste de regex; dado nunca se perde |
| SEFAZ-SC indisponível/captcha | chave de acesso salva, botão "tentar de novo"; plano B documentado: fetch no client (browser do usuário) e envio do HTML ao backend |
| OFX com encoding/formato inesperado | parser tolerante; rejeita linha a linha com relatório, nunca aborta o import inteiro |
| Push falha (subscription expirada) | remove subscription inválida; resumo continua visível no Dashboard |
| Dedup incorreto (FITID instável) | fallback por hash; import reporta contagens para auditoria visual |

## 9. Testes

- **Unit (fixtures reais, anonimizadas):** parser OFX com arquivos reais do BB e da Caixa; parser SMS com ≥3 mensagens reais do cartão Caixa; parser NFC-e com HTML real da SEFAZ-SC; dedup (reimport sobreposto); regra `is_invoice_payment`; conciliação cupom↔transação (match exato, ±1 dia, ambíguo, sem match).
- **Integração:** import OFX → enriquecimento → endpoints do dashboard retornando agregações corretas; ingest SMS → transação visível; fluxo de push (mock).
- **Aceitação real (gate da rodada):** OFX real dos dois bancos importado; um SMS real entregue via Atalho; um cupom real de mercado escaneado e conciliado; resumo semanal recebido no iPhone.

## 10. Fora de escopo (rodada 1)

- Auth multiusuário, cadastro, billing/Freemium, onboarding
- Agregador Open Finance (Pluggy/Meu Pluggy) — entra como 4º canal de ingestão quando fizer sentido
- NFC-e de outros estados além de SC
- Chat conversacional e alertas threshold-based (rodada 2; decisões de abril continuam válidas)
- App nativo iOS/Android
- CSV (continua fora, como decidido em abril)

## 11. Riscos conhecidos

| Risco | Mitigação |
|---|---|
| SEFAZ-SC muda layout ou adiciona captcha | HTML cru em `raw_events` permite reprocessar; plano B via fetch no client |
| Caixa muda formato do SMS | raw sempre salvo; regex ajustável + reprocesso |
| Disciplina de exportar OFX a cada 2 semanas | janela de 60 dias dá folga; lembrete mensal opcional via push se não houver import há 30 dias |
| Push no iOS exige PWA instalada | passo do setup pessoal documentado no plano de implementação |
| Dependência do OpenRouter | provedor de IA é configuração; troca por Anthropic API direta sem mudança de arquitetura |

## 12. Preparação para a fase SaaS (sem construir agora)

Esta rodada deixa pronto: `user_id` em todas as tabelas; ingestão modelada como canais plugáveis; front React reaproveitável; NFC-e por estratégia-por-UF; regra de negócio (enriquecimento, resumo) independente da fonte de dados. A decisão agregador-pago vs. instituição autorizada fica para quando houver tração.
