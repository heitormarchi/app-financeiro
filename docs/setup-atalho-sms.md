# Atalho iOS — ingest de SMS do cartão Caixa

Automação no app Atalhos (Shortcuts) do iOS que envia cada SMS recebido do
remetente "CAIXA" para o backend, criando uma transação provisória
(`status=provisoria`, `source_channel=sms`) em tempo real, antes mesmo da
fatura fechar.

## Passo a passo

1. App **Atalhos** → aba **Automação** → **Nova Automação Pessoal**.
2. Gatilho: **Mensagem** → **Quando eu receber uma mensagem** → em
   "Remetente", selecionar **contém** → `CAIXA`.
3. Desmarcar "Perguntar antes de executar" (para rodar em segundo plano, sem
   interação do usuário).
4. Ação: **Obter Conteúdo de URL**
   - URL: `https://<dominio>/api/v1/ingest/sms`
   - Método: `POST`
   - Cabeçalhos:
     - `X-API-Key`: `<a mesma API key configurada no backend>`
     - `Content-Type`: `application/json`
   - Corpo (JSON):
     ```json
     {
       "text": "Mensagem do Atalho (variável 'Conteúdo da Mensagem')",
       "received_at": "Data Atual (formato ISO 8601)"
     }
     ```
     No editor de Atalhos, usar as variáveis mágicas: `Conteúdo da Mensagem`
     para `text` e `Data Atual` (formatada como ISO 8601) para `received_at`.

## Comportamento esperado

- SMS reconhecido → `200 OK`, cria (ou identifica como duplicata) a
  transação provisória.
- SMS em formato não reconhecido (ex.: promoções, avisos) → `202 Accepted`,
  vira `Pendencia(type=parse_failed)` para revisão manual — não trava o
  Atalho nem gera erro visível.

## Formato de SMS suportado

```
CAIXA: Compra aprovada em <ESTABELECIMENTO>, R$ <VALOR>, <DD>/<MM> as <HH>:<MM>. VISA[ VIRTUAL] final <XXXX>. Nao reconhece? Envie BL<XXXX> p/cancelar cartao
```

Baseado em amostras reais anonimizadas (ver
`backend/tests/fixtures/sms_caixa_anon.txt`). Se o formato divergir no
futuro (mudança do banco), ajustar a regex em
`backend/app/services/parsers/sms_parser.py`.
