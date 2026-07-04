# Rodada 1 — Uso pessoal: multi-canal de ingestão + PWA + previsão de saldo

**Data:** 2026-07-04 (v2 — incorpora "specs heitor": fatura PDF, WhatsApp, Inter Empresas, futuros)
**Status:** Em revisão pelo Heitor
**Escopo:** design da rodada 1 (uso pessoal). Sem desenvolvimento nesta fase.
**Objetivo macro:** simplicidade.

## 1. Contexto e objetivo

O app-financeiro tinha arquitetura voltada a B2C via Pluggy (agregador Open Finance). Esta rodada reposiciona o projeto: **primeiro resolver a organização financeira pessoal do Heitor**, com custo próximo de zero e sem intermediários, mantendo o caminho aberto para a fase SaaS (mercado brasileiro, Freemium).

**Critérios de sucesso da rodada 1:**
1. Heitor sabe onde gasta — dashboard por categoria + resumo semanal por push, sem lançamento manual.
2. Visão "junto, mas separado" de pessoal (BB, Caixa) e empresa (Inter PJ).
3. O app antecipa saldo baixo (lançamentos futuros) e sugere transferência da empresa, executável no próprio app com confirmação.

### Por que não Open Finance direto

O Open Finance Brasil é um ecossistema fechado regulado pelo BACEN: só instituições autorizadas e registradas no Diretório de Participantes recebem dados de clientes (ICP-Brasil, FAPI-BR, compliance). Pessoa física/dev solo não se qualifica; a API de Extratos do BB atende apenas contas PJ do CNPJ dono da aplicação. Decisão: **OFX manual + fatura PDF + SMS + API oficial do Inter PJ** são os canais diretos viáveis. Agregadores (Pluggy/Meu Pluggy) ficam como upgrade futuro opcional.

## 2. Decisões desta rodada

| Tema | Decisão |
|---|---|
| Contas cobertas | BB conta (pessoal), Caixa conta (pessoal), Cartão Caixa (pessoal), **Inter Empresas (PJ)** |
| Ingestão | OFX (BB/Caixa conta) + **fatura PDF Caixa** + SMS cartão via Atalho iOS + NFC-e QR (SC) + **API Inter PJ** + **WhatsApp (Evolution API) como transporte universal** |
| Interface | PWA (React SPA via Vite) servida pelo FastAPI na VPS; **menu inferior com ícones + "..."** |
| Backend existente | Reaproveitar e podar: mantém models/enrichment/insight; aposenta `pluggy_service` e Supabase Auth |
| Auth | Single-user por API key estática (multiusuário volta na fase SaaS) |
| Entrega de valor | Dashboard + resumo semanal push + **alertas de saldo baixo com sugestão de transferência** |
| Transferências | Sugestão + **confirmação explícita** no app → Pix via API Inter (nunca automático) |
| Scheduler | APScheduler embutido no FastAPI |
| IA | `insight_service` no OpenRouter (texto); **modelo com visão para prints** (ex.: tela Futuros do BB); troca de provedor é configuração |
| Build | **Faseado: R1a (núcleo) → R1b (WhatsApp + Inter + futuros + transferências)** |

## 3. Arquitetura

```
iPhone (Safari/PWA) ──┐
Windows (browser) ────┤
Atalho iOS (SMS) ─────┼──▶ FastAPI (VPS/EasyPanel) ──▶ PostgreSQL (VPS)
WhatsApp ─▶ Evolution ┘        ├ /api/v1/* (JSON)
                               ├ /         (React dist/)
Inter Empresas API ◀───mTLS────┤ APScheduler (in-process)
SEFAZ-SC (NFC-e) ◀──HTTP───────┘
```

- Monorepo: `backend/` (FastAPI) + `frontend/` (Vite + React + TS) + `docs/`.
- Um único serviço de deploy; HTTPS pelo EasyPanel (necessário p/ service worker/push).
- **Entidades:** toda fonte e transação tem `entity` = `pessoal` | `empresa`. Dashboard com seletor Pessoal / Empresa / Consolidado — "junto, mas separado".

### Autenticação e segredos

- `APP_API_KEY` no `.env`; PWA guarda em localStorage; Atalho iOS envia no header `X-API-Key`; comparação constant-time.
- Certificado mTLS do Inter (`.crt`/`.key`, validade 12 meses, gerado no portal Inter Empresas) armazenado na VPS, fora do git.
- **Senhas de PDF**: tela de Config → senha por fonte (ex.: fatura Caixa = CPF), criptografadas at rest (Fernet com chave derivada do `.env`). Nunca em texto plano no banco.
- Webhook do WhatsApp: aceita apenas mensagens do número do Heitor (allowlist de JID) + token secreto na URL do webhook.

## 4. Ingestão de dados

Princípio comum a todos os canais: **payload cru sempre persistido em `raw_events` antes do parse**. Parse falhou → pendência visível e reprocessável; dado nunca se perde. Cada canal reporta `{novas, duplicadas, rejeitadas}`.

### 4.1 OFX (BB conta + Caixa conta)

- Upload no PWA ou envio pelo WhatsApp. Parser `ofxparse`, tolerante a encoding (`latin-1`/`cp1252`).
- **Peculiaridades reais do OFX BB** (validadas com `docs/exemplos/Extrato conta corrente - 072026.ofx`):
  - Pseudo-transações "Saldo Anterior" / "Saldo do dia" (valor 0,00, FITID vazio) → filtradas.
  - Datas inválidas (ex.: `00021130...`) → linha rejeitada com relatório, sem abortar o import.
  - **Lançamentos futuros aparecem no extrato** (data > hoje) → viram `scheduled_transactions`, não gastos realizados.
- Dedup: `(conta, FITID)`; fallback hash `(data, valor, memo normalizado)`. Reimports sobrepostos nunca duplicam.

### 4.2 Fatura do cartão Caixa em PDF

A Caixa não entrega OFX de cartão; a fatura PDF é o fechamento mensal autoritativo. Layout validado com `docs/exemplos/fatura.pdf` (senha = CPF do titular):

- Abertura com senha configurada (pypdf/pikepdf); extração de texto por página.
- Seções por cartão (pode haver mais de um, ex.: finais 3136 e 6425): COMPRAS, COMPRAS PARCELADAS, ajustes.
- Linha: `DD/MM DESCRIÇÃO CIDADE [U$$ COTAÇÃO VALOR_ORIG] VALOR D|C` (colunas de moeda estrangeira opcionais).
- **Parceladas**: `GIASSI SUPERMERCADOS 06 DE 07` → transação da parcela do mês com `installment_no=6`, `installment_total=7`, `original_purchase_date` (data mostrada é a da compra original).
- Linhas informativas filtradas: `TOTAL DA FATURA ANTERIOR`, `OBRIGADO PELO PAGAMENTO`, `AJUSTE CRED*` (ajustes viram créditos, não compras), totais de seção.
- **Metadados aproveitados**: vencimento, valor total, "DESPESAS A VENCER" e "Saldo previsto próxima fatura" alimentam a previsão de saldo (§7).
- Dedup por hash `(cartão, data, descrição, valor, parcela)`.

### 4.3 SMS do cartão Caixa (tempo real)

- `POST /api/v1/ingest/sms` — body `{text, received_at}`, header `X-API-Key`.
- Origem: automação do Atalhos iOS "Ao receber mensagem" (filtro CAIXA) → POST. Roda sem confirmação.
- Cria transação `source=sms` com status **provisória**; parser calibrado com ≥3 SMS reais como fixtures.
- **Conciliação SMS ↔ fatura**: quando a fatura do mês é importada, cada linha procura a transação provisória correspondente (valor exato + data ±1 dia + similaridade de estabelecimento) e a **confirma** (evita duplicidade). Linha sem par cria transação nova; SMS sem par na fatura vira pendência ("compra não apareceu na fatura").
- **Anti-dupla-contagem**: o débito de pagamento da fatura no extrato da conta Caixa (ex.: "PAG FATURA CARTAO") recebe `is_invoice_payment=true` e é excluído de todas as agregações de gasto — as compras já entraram individualmente via SMS/fatura.

### 4.4 NFC-e via QR (Santa Catarina)

- Câmera no PWA (BarcodeDetector; fallback jsQR) ou **foto do cupom via WhatsApp** (decode do QR server-side com pyzbar).
- Backend consulta o portal público da SEFAZ-SC (`sat.sef.sc.gov.br`), extrai emitente, data, total e **itens** (descrição, código, qtd, unidade, valores).
- Conciliação cupom ↔ transação: data ±1 dia + valor total ±R$ 0,01; achou → anexa `receipt_items`; não achou → cria `source=nfce`.
- **Mapeamento item → categoria**: tabela de regras próprias no nível de item (ex.: "LEITE UHT" → Mercado/Laticínios), editável na UI. Item genérico/ilegível → **pendência para o usuário descrever** (uma vez descrito, vira regra).
- Parser como estratégia-por-UF (SC primeiro). Risco captcha → plano B: fetch no client e envio do HTML.

### 4.5 Inter Empresas (API oficial, automático)

- Fonte `entity=empresa`. APIs usadas: **Extrato/Saldo** (sync diário via APScheduler), **Pagamentos agendados** (alimenta futuros), **Pix** (execução de transferência, §7).
- Auth: OAuth2 + certificado mTLS emitido no portal Inter Empresas (renovação anual — lembrete automático por push 30 dias antes de expirar).
- **Limitação registrada**: a API do Inter não expõe investimentos; saldo investido não é acessível programaticamente (aparece no extrato apenas em aplicação/resgate). Reavaliar periodicamente.
- Dedup por ID da transação retornado pela API.

### 4.6 WhatsApp como transporte universal (Evolution API)

O Heitor já roda Evolution API no WhatsApp pessoal. Fluxo: **encaminhar qualquer documento para o próprio bot** → webhook no backend → roteamento por tipo:

| Conteúdo | Rota |
|---|---|
| `.ofx` | parser OFX (§4.1) |
| `.pdf` | parser de fatura (§4.2), tentando as senhas configuradas |
| Imagem com QR legível | pipeline NFC-e (§4.4) |
| Imagem sem QR (ex.: print "Futuros" do BB) | **LLM com visão** extrai lançamentos estruturados → `scheduled_transactions` (validado com `docs/exemplos/WhatsApp Image...jpeg`) |
| Qualquer falha | `raw_events` + resposta no próprio WhatsApp ("não entendi este arquivo") |

- O bot **responde no WhatsApp** com o resultado ("42 transações novas importadas" / "cupom conciliado com compra de R$ 118,54 no Bistek").
- Caso de uso primário: exportar OFX no iPhone → compartilhar direto no WhatsApp, sem passar pelo PC.

## 5. Modelo de dados (delta sobre o schema atual)

| Tabela | Mudança |
|---|---|
| `transactions` | + `source` (`ofx`, `pdf`, `sms`, `nfce`, `inter`); + `entity` (`pessoal`, `empresa`); + `external_id`; + `status` (`provisoria`, `confirmada`); + `is_invoice_payment`; + `installment_no`, `installment_total`, `original_purchase_date` (nullable) |
| `scheduled_transactions` | **nova**: `due_date`, `description`, `amount`, `source_account`, `origin` (`ofx_futuro`, `print_vision`, `inter_agendado`, `fatura_a_vencer`), `status` (`previsto`, `efetivado`, `cancelado`), FK transação efetivada |
| `receipt_items` | **nova**: FK transação, `description`, `product_code`, `quantity`, `unit`, `unit_price`, `total_price`, `category` |
| `item_category_rules` | **nova**: padrão de item → categoria (feedback loop no nível de item) |
| `raw_events` | **nova**: `type` (`sms`, `nfce`, `ofx`, `pdf`, `whatsapp_image`), `transport` (`upload`, `atalho`, `whatsapp`), `payload`, `status` (`parsed`, `failed`), FK transação |
| `pendencias` | **nova**: `type` (`parse_failed`, `item_generico`, `sms_sem_fatura`, `descrever_lancamento`), payload, `resolved` |
| `push_subscriptions` | **nova**: endpoint + keys VAPID por dispositivo |
| `sources` (ex-`bank_connections`) | cadastro das fontes com `entity`, `type` (`bb_conta`, `caixa_conta`, `caixa_cartao`, `inter_pj`), senha PDF criptografada (nullable), config Inter (cert path) |
| `transfer_suggestions` | **nova**: data, valor sugerido, motivo (projeção), status (`sugerida`, `confirmada`, `executada`, `recusada`), id do Pix na API Inter |
| `users`, `user_routines` | mantidas; `collective_patterns` dormente |

Migrações via Alembic.

## 6. Enriquecimento e IA

- Pipeline existente mantido (dicionário regex → inferência temporal → LLM para o resto). SMS traz estabelecimento limpo; NFC-e traz itens; fatura traz cidade — entradas melhores, menos LLM.
- **Feedback loop em dois níveis**: correção de categoria da transação e do item de cupom viram regras persistentes.
- **Resumo semanal** (domingo 18h, America/Sao_Paulo): agrega semana vs. médias 30/90d, separado por entidade (pessoal/empresa), 3–4 frases em PT-BR via `insight_service`; entregue por web push (pywebpush + VAPID) e persistido no Dashboard.
- **Visão**: prints (tela Futuros BB) processados por modelo multimodal via OpenRouter; saída estruturada (JSON de lançamentos) validada por Pydantic antes de persistir.

## 7. Futuros e previsão de saldo (a feature "conselheiro")

1. `scheduled_transactions` agrega futuros de 4 origens: OFX BB (lançamentos com data futura), print Futuros via visão, agendamentos da API Inter, e "despesas a vencer"/vencimento da fatura Caixa.
2. Projeção diária de saldo por conta: saldo atual − futuros até D+30.
3. Projeção cruza limiar (default R$ 0; configurável) → **push**: "Saldo BB ficará −R$ 320 em 16/07 (Pix agendado + 2 boletos). Transferir R$ 500 do Inter Empresas?"
4. Tela de revisão: valor editável, origem/destino visíveis → **[Confirmar]** → Pix executado pela API do Inter → comprovante registrado, futuro marcado como coberto.
5. **Guarda-corpos**: nunca automático; confirmação explícita a cada transferência; log completo em `transfer_suggestions`; falha da API Inter → sugestão permanece com aviso para fazer manualmente.
6. Efetivação: quando a transação real chega (extrato), o `scheduled_transaction` correspondente é marcado `efetivado` (match valor+data ±2 dias).

## 8. PWA — navegação e telas

**Menu inferior fixo com ícones**: `Dashboard · Transações · [+] · Futuros · ...`

- **[+] central**: ações rápidas — escanear cupom, importar OFX/PDF.
- **"..."**: Pendências, Config (push, API key, senhas de PDF, fontes, certificado Inter).

Telas:
1. **Dashboard** — seletor Pessoal/Empresa/Consolidado; gasto do mês por categoria (donut), evolução mensal (barras), top 5, último resumo semanal, cartão de alerta de saldo (se houver).
2. **Transações** — filtros (mês, categoria, fonte, entidade), edição de categoria inline, badge provisória/confirmada, expansão para itens de cupom com edição de categoria por item.
3. **Futuros** — linha do tempo de lançamentos futuros + gráfico de projeção de saldo por conta + sugestões de transferência (revisar/confirmar/recusar).
4. **Cupom/Importar** (via [+]) — câmera QR; upload OFX/PDF com resultado do dedup.
5. **Pendências** — parse failures, itens genéricos a descrever, SMS sem par na fatura; cada uma com ação de resolver.
6. **Config** — push por dispositivo, API key, senhas de PDF por fonte, status do certificado Inter, saúde dos canais (último sync/import por fonte).

Gráficos: Recharts. PWA: manifest + service worker (push + cache estático).

## 9. Tratamento de erros

| Falha | Comportamento |
|---|---|
| Parse falhou (qualquer canal) | `raw_events.status=failed` + pendência; reprocessável após ajuste; dado nunca se perde |
| PDF com senha errada/ausente | pendência "configurar senha da fonte X"; reprocessa ao salvar senha |
| SEFAZ-SC indisponível/captcha | chave salva + retry; plano B: fetch no client |
| WhatsApp: remetente não autorizado | ignorado e logado; sem resposta |
| API Inter fora / cert expirado | sync marca fonte como degradada (visível em Config); push avisa se >48h sem sync; lembrete de renovação do cert 30 dias antes |
| Pix de transferência falha | sugestão permanece aberta com erro legível; instrução para fazer manual no app Inter |
| Push falha (subscription expirada) | remove subscription; conteúdo continua no app |
| Dedup incorreto | contagens de import visíveis para auditoria |

## 10. Testes

- **Unit (fixtures reais de `docs/exemplos/`)**: OFX BB (pseudo-transações, data inválida, futuros); fatura PDF (senha, seções multi-cartão, parceladas "NN DE MM", ajustes, moeda estrangeira, metadados a vencer); SMS (≥3 reais); HTML SEFAZ-SC; print Futuros (saída da visão validada por Pydantic); dedup por canal; conciliação SMS↔fatura (match, sem par, ambíguo); regra `is_invoice_payment`; projeção de saldo.
- **Integração**: cada canal → enriquecimento → agregações do dashboard; webhook WhatsApp com roteamento por tipo; fluxo sugestão→confirmação→Pix (API Inter mockada).
- **Aceitação real (gate)**: OFX real importado pelos dois caminhos (upload e WhatsApp); fatura real parseada com senha; SMS real via Atalho; cupom real conciliado; print Futuros virando lançamentos; resumo semanal no iPhone; uma transferência real de valor baixo (ex.: R$ 1,00) Inter→BB confirmada no app.

## 11. Ordem de build (R1a → R1b)

**R1a — núcleo usável** (Heitor começa a usar aqui):
1. Poda do backend + migrações do novo schema
2. Parsers OFX + fatura PDF + SMS; conciliação; regra fatura
3. PWA: menu inferior, Dashboard, Transações, Importar, Config (inclui senhas PDF), Pendências
4. Cupom NFC-e (câmera + SEFAZ-SC + itens + regras de categoria por item)
5. Resumo semanal + web push

**R1b — automação e empresa**:
6. Webhook WhatsApp (Evolution) com roteamento completo + respostas no chat
7. Visão para prints (Futuros BB)
8. Inter Empresas: extrato/saldo + agendamentos (entity empresa no dashboard)
9. Futuros + projeção de saldo + sugestões
10. Execução de transferência via Pix Inter (com aceitação real de R$ 1,00)

## 12. Fora de escopo (registrado para o futuro)

- Auth multiusuário, billing/Freemium, onboarding, app nativo (fase SaaS)
- Agregador Open Finance (Pluggy/Meu Pluggy) como canal adicional
- NFC-e de outros estados; CSV
- Chat conversacional; alertas threshold por categoria (decisões de abril continuam válidas para a rodada 2)
- **Integrações iFood / Mercado Livre / Shopee e outros apps de compra** — objetivo: melhorar categorização com dados do pedido (registrado a pedido do Heitor, sem data)
- Investimentos Inter via API (indisponível hoje — reavaliar)

## 13. Riscos conhecidos

| Risco | Mitigação |
|---|---|
| SEFAZ-SC muda layout/captcha | raw salvo; plano B client-side |
| Caixa muda formato do SMS ou da fatura | raw salvo; parsers versionados; pendência sinaliza na hora |
| Layout do print BB muda | visão por LLM é tolerante a layout; validação Pydantic barra lixo |
| Cert Inter expira (12 meses) | lembrete push 30 dias antes; status em Config |
| Evolution API fora do ar | WhatsApp é transporte, não fonte — tudo tem caminho alternativo pelo PWA |
| Disciplina de exportar OFX | janela de 60 dias; push se >30 dias sem import |
| Mover dinheiro via API | nunca automático; confirmação explícita; log completo; teste real com R$ 1,00 |
| Dependência do OpenRouter | provedor é configuração; troca por Anthropic direto sem rearquitetura |

## 14. Preparação para a fase SaaS

Fica pronto de graça: `user_id` + `entity` em tudo; ingestão como canais plugáveis (agregador entra como canal novo); front React reaproveitável; NFC-e estratégia-por-UF; parser de fatura extensível a outros emissores; WhatsApp bot já é um canal de produto (diferencial B2C no Brasil). Decisão agregador-pago vs. instituição autorizada fica para quando houver tração.
