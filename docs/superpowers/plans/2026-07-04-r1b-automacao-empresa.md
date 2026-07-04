# R1b — Automação e Empresa: Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WhatsApp como canal universal de ingestão, visão para prints, Inter Empresas sincronizado via API, projeção de saldo com sugestão de transferência e execução de Pix com confirmação explícita.

**Architecture:** Estende o R1a: novo webhook (Evolution API) roteando documentos para os parsers existentes; cliente Inter (OAuth2 + mTLS) com sync diário via APScheduler; serviço de projeção que consome `scheduled_transactions` + saldos conhecidos e alimenta `transfer_suggestions`; Pix sai pela API do Inter somente após confirmação no PWA.

**Tech Stack:** os do R1a + pyzbar + Pillow (QR em imagem), httpx com `cert=` (mTLS Inter), modelo multimodal via OpenRouter.

**Spec:** `docs/superpowers/specs/2026-07-04-rodada1-pessoal-design.md`
**Pré-requisito:** plano R1a (`2026-07-04-r1a-nucleo.md`) completo — modelos, parsers, `import_service`, `push_service`, PWA.

## Global Constraints

- Todas as do R1a permanecem (PT-BR, raw-first, dedup, API key, entity).
- Webhook WhatsApp: aceita SOMENTE mensagens do JID do Heitor (`WHATSAPP_ALLOWED_JID`) e com token secreto na URL; qualquer outra origem → 200 silencioso (não vaza existência) + log.
- Transferência NUNCA automática: `TransferSuggestion.status` só vira `executada` via `POST /transfers/{id}/confirm` disparado pelo usuário no PWA.
- Endpoints/formatos da Evolution API variam por versão — validar contra a instância do Heitor no Step 1 da Task 1 antes de fixar payloads.
- Novos segredos no `.env`: `EVOLUTION_BASE_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`, `EVOLUTION_WEBHOOK_TOKEN`, `WHATSAPP_ALLOWED_JID`, `INTER_CLIENT_ID`, `INTER_CLIENT_SECRET`, `INTER_CERT_PATH`, `INTER_KEY_PATH`, `INTER_PIX_DEST_KEY` (chave Pix pessoal destino), `OPENROUTER_VISION_MODEL` (default `google/gemini-2.0-flash-001`).

---

### Task 1: Config estendido + webhook WhatsApp com segurança

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/api/v1/endpoints/webhooks.py`
- Create: `backend/app/services/whatsapp_service.py`
- Modify: `backend/app/api/v1/router.py` (webhook fica FORA do `protected` — segurança própria por token+JID)
- Test: `backend/tests/test_whatsapp_webhook.py`

**Interfaces:**
- Produces: `POST /api/v1/webhooks/whatsapp/{token}` (payload Evolution `messages.upsert`); `whatsapp_service.send_text(text: str) -> None` (responde ao Heitor); `whatsapp_service.get_media_bytes(message_data: dict) -> tuple[bytes, str]` (conteúdo + mimetype); `handle_incoming(session, data: dict) -> str | None` (resposta a enviar).

- [ ] **Step 1: Validar contra a instância real.** Com a Evolution do Heitor rodando: configurar webhook para URL de teste, enviar um documento e capturar o JSON real (salvar anonimizado em `backend/tests/fixtures/evolution_document.json` e `evolution_image.json`). Confirmar endpoints da versão instalada: envio de texto (`POST {base}/message/sendText/{instance}`, header `apikey`) e download de mídia (`POST {base}/chat/getBase64FromMediaMessage/{instance}`). Ajustar os stubs abaixo se divergirem.

- [ ] **Step 2: Config** — adicionar ao `Settings`:

```python
    evolution_base_url: str = ""
    evolution_api_key: str = ""
    evolution_instance: str = ""
    evolution_webhook_token: str = ""
    whatsapp_allowed_jid: str = ""
    inter_client_id: str = ""
    inter_client_secret: str = ""
    inter_cert_path: str = ""
    inter_key_path: str = ""
    inter_pix_dest_key: str = ""
    openrouter_vision_model: str = "google/gemini-2.0-flash-001"
```

- [ ] **Step 3: Testes falhando** — `backend/tests/test_whatsapp_webhook.py`:

```python
import json
from pathlib import Path

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "evolution_document.json").read_text(encoding="utf-8"))


async def test_token_errado_404(client):
    r = await client.post("/api/v1/webhooks/whatsapp/token-errado", json=FIXTURE)
    assert r.status_code == 404


async def test_jid_nao_autorizado_ignorado(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "evolution_webhook_token", "tok")
    monkeypatch.setattr(settings, "whatsapp_allowed_jid", "5548999990000@s.whatsapp.net")
    payload = json.loads(json.dumps(FIXTURE))
    payload["data"]["key"]["remoteJid"] = "5511888887777@s.whatsapp.net"
    r = await client.post("/api/v1/webhooks/whatsapp/tok", json=payload)
    assert r.status_code == 200 and r.json() == {"ok": True}  # silencioso


async def test_documento_ofx_roteado(client, session, monkeypatch):
    from app.core.config import settings
    from app.services import whatsapp_service
    monkeypatch.setattr(settings, "evolution_webhook_token", "tok")
    monkeypatch.setattr(settings, "whatsapp_allowed_jid", FIXTURE["data"]["key"]["remoteJid"])
    ofx = (Path(__file__).parent / "fixtures" / "bb_extrato_anon.ofx").read_bytes()

    async def fake_media(data):
        return ofx, "application/octet-stream"
    sent: list[str] = []

    async def fake_send(text):
        sent.append(text)
    monkeypatch.setattr(whatsapp_service, "get_media_bytes", fake_media)
    monkeypatch.setattr(whatsapp_service, "send_text", fake_send)
    # seed da fonte BB
    from app.core.auth import get_single_user
    from app.models.models import Entity, Source, SourceType
    user = await get_single_user(session)
    session.add(Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal, bank_name="BB"))
    await session.commit()
    r = await client.post("/api/v1/webhooks/whatsapp/tok", json=FIXTURE)
    assert r.status_code == 200
    assert sent and "novas" in sent[0]
```

- [ ] **Step 4: Rodar e ver falhar.**

- [ ] **Step 5: Implementar** — `whatsapp_service.py`:

```python
import base64

import httpx

from app.core.config import settings


async def send_text(text: str) -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        await c.post(
            f"{settings.evolution_base_url}/message/sendText/{settings.evolution_instance}",
            headers={"apikey": settings.evolution_api_key},
            json={"number": settings.whatsapp_allowed_jid.split("@")[0], "text": text})


async def get_media_bytes(message_data: dict) -> tuple[bytes, str]:
    msg = message_data.get("message", {})
    mime = (msg.get("documentMessage") or msg.get("imageMessage") or {}).get("mimetype", "")
    async with httpx.AsyncClient(timeout=60) as c:
        resp = await c.post(
            f"{settings.evolution_base_url}/chat/getBase64FromMediaMessage/{settings.evolution_instance}",
            headers={"apikey": settings.evolution_api_key},
            json={"message": message_data})
        resp.raise_for_status()
        return base64.b64decode(resp.json()["base64"]), mime
```

`endpoints/webhooks.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.services import whatsapp_service
from app.services.document_router import route_document  # Task 2

router = APIRouter(prefix="/webhooks")


@router.post("/whatsapp/{token}")
async def whatsapp_webhook(token: str, request: Request,
                           session: AsyncSession = Depends(get_session)):
    if not settings.evolution_webhook_token or token != settings.evolution_webhook_token:
        raise HTTPException(404)
    body = await request.json()
    data = body.get("data", {})
    jid = data.get("key", {}).get("remoteJid", "")
    if jid != settings.whatsapp_allowed_jid or data.get("key", {}).get("fromMe"):
        return {"ok": True}
    msg = data.get("message", {})
    doc = msg.get("documentMessage") or msg.get("imageMessage")
    if not doc:
        return {"ok": True}  # texto puro: ignorado no R1b
    content, mime = await whatsapp_service.get_media_bytes(data)
    filename = (msg.get("documentMessage") or {}).get("fileName", "imagem.jpg")
    reply = await route_document(session, filename, content, mime)
    if reply:
        await whatsapp_service.send_text(reply)
    return {"ok": True}
```

- [ ] **Step 6: Rodar testes** → 3 PASS. **Step 7: Commit** — `git commit -m "feat: webhook whatsapp evolution com token e allowlist"`

---

### Task 2: Roteador de documentos (OFX / PDF / imagem)

**Files:**
- Create: `backend/app/services/document_router.py`
- Modify: `backend/requirements.txt` (adicionar `pyzbar==0.1.9`, `Pillow==11.0.0`; nota: pyzbar requer `libzbar0` no container — adicionar `apt-get install -y libzbar0` no Dockerfile)
- Test: `backend/tests/test_document_router.py`

**Interfaces:**
- Consumes: `import_ofx`, `import_fatura` (R1a Task 4/6), `process_nfce` (R1a Task 8), `extract_scheduled_from_image` (Task 3 — nesta task, stub que levanta `NotImplementedError` capturado como resposta "ainda não sei ler este print").
- Produces: `route_document(session, filename: str, content: bytes, mimetype: str) -> str` — SEMPRE retorna resposta humana em PT-BR; nunca levanta exceção (erros viram resposta + `Pendencia`).

- [ ] **Step 1: Testes falhando** — `backend/tests/test_document_router.py`:

```python
from pathlib import Path

from app.services.document_router import route_document

OFX = (Path(__file__).parent / "fixtures" / "bb_extrato_anon.ofx").read_bytes()


async def test_ofx_identifica_banco_pelo_conteudo(client, session):
    from app.core.auth import get_single_user
    from app.models.models import Entity, Source, SourceType
    user = await get_single_user(session)
    session.add(Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal, bank_name="BB"))
    await session.commit()
    reply = await route_document(session, "extrato.ofx", OFX, "application/octet-stream")
    assert "novas" in reply


async def test_arquivo_desconhecido_gera_resposta_e_pendencia(client, session):
    from sqlalchemy import select
    from app.models.models import Pendencia
    reply = await route_document(session, "dado.xyz", b"binario", "application/zip")
    assert "não" in reply.lower()
    assert (await session.execute(select(Pendencia))).scalars().first() is not None
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar** — `document_router.py`:

```python
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.models.models import Pendencia, PendenciaType, Source, SourceType, Transport
from app.services.import_service import import_fatura, import_ofx
from app.services.nfce_service import process_nfce
from app.services.parsers.fatura_parser import PdfPasswordError


async def _source_by_type(session, t: SourceType) -> Source | None:
    return (await session.execute(select(Source).where(Source.type == t))).scalar_one_or_none()


def _detect_ofx_source_type(content: bytes) -> SourceType:
    head = content[:2000].decode("utf-8", errors="replace").upper()
    return SourceType.bb_conta if "BANCO DO BRASIL" in head else SourceType.caixa_conta


async def route_document(session: AsyncSession, filename: str, content: bytes,
                         mimetype: str) -> str:
    name = filename.lower()
    try:
        if name.endswith(".ofx") or b"OFXHEADER" in content[:200]:
            src = await _source_by_type(session, _detect_ofx_source_type(content))
            if src is None:
                return "Fonte bancária não cadastrada — configure em Config."
            r = await import_ofx(session, src, content, Transport.whatsapp)
            return (f"Extrato {src.bank_name}: {r.novas} novas, {r.duplicadas} duplicadas, "
                    f"{r.rejeitadas} rejeitadas, {r.futuros} futuros.")
        if name.endswith(".pdf") or mimetype == "application/pdf":
            src = await _source_by_type(session, SourceType.caixa_cartao)
            try:
                r = await import_fatura(session, src, content, Transport.whatsapp)
            except PdfPasswordError:
                return "Não consegui abrir o PDF — confira a senha da fatura em Config."
            return f"Fatura: {r.novas} novas, {r.duplicadas} conciliadas/duplicadas."
        if mimetype.startswith("image/"):
            qr_url = _try_decode_qr(content)
            if qr_url and "sat.sef.sc.gov.br" in qr_url:
                res = await process_nfce(session, qr_url, Transport.whatsapp)
                if res.get("parsed"):
                    extra = " (conciliado ✓)" if res.get("conciliada") else ""
                    return f"Cupom lido: {res['itens']} itens{extra}."
                return "Cupom recebido mas a SEFAZ não respondeu — ficou nas pendências."
            from app.services.vision_service import extract_scheduled_from_image
            n = await extract_scheduled_from_image(session, content)
            return f"Print lido: {n} lançamentos futuros registrados."
    except Exception as e:  # nunca propagar para o webhook
        user = await get_single_user(session)
        session.add(Pendencia(user_id=user.id, type=PendenciaType.parse_failed,
                              payload={"canal": "whatsapp", "arquivo": filename, "erro": str(e)}))
        await session.commit()
        return "Não consegui processar este arquivo — ficou registrado nas pendências."
    user = await get_single_user(session)
    session.add(Pendencia(user_id=user.id, type=PendenciaType.parse_failed,
                          payload={"canal": "whatsapp", "arquivo": filename, "erro": "tipo desconhecido"}))
    await session.commit()
    return "Não reconheci este tipo de arquivo (aceito: OFX, PDF de fatura, foto de cupom ou print)."


def _try_decode_qr(content: bytes) -> str | None:
    from PIL import Image
    from pyzbar.pyzbar import decode
    codes = decode(Image.open(io.BytesIO(content)))
    for c in codes:
        text = c.data.decode("utf-8", errors="replace")
        if text.startswith("http"):
            return text
    return None
```

- [ ] **Step 4: Rodar testes** → 2 PASS. **Step 5: Commit** — `git commit -m "feat: roteador de documentos do whatsapp"`

---

### Task 3: Visão — print de lançamentos futuros

**Files:**
- Create: `backend/app/services/vision_service.py`
- Test: `backend/tests/test_vision.py`

**Interfaces:**
- Produces: `extract_scheduled_from_image(session, image: bytes) -> int` (nº de futuros criados) e `parse_vision_json(raw: str) -> list[VisionScheduled]` com `VisionScheduled(due_date: date, description: str, amount: Decimal)` (Pydantic, valores negativos = débito). Dedup igual ao de `ScheduledTransaction` do R1a (data+valor+descrição).

- [ ] **Step 1: Testes falhando** — `backend/tests/test_vision.py`:

```python
from app.services.vision_service import parse_vision_json


def test_parse_json_valido():
    raw = '{"lancamentos": [{"due_date": "2026-07-10", "description": "PAG BOLETO MY DOGGIE", "amount": -690.00}]}'
    items = parse_vision_json(raw)
    assert len(items) == 1 and float(items[0].amount) == -690.00


def test_json_com_lixo_em_volta():
    raw = 'Aqui está:\n```json\n{"lancamentos": [{"due_date": "2026-07-15", "description": "CLARO", "amount": -81.90}]}\n```'
    assert len(parse_vision_json(raw)) == 1


def test_json_invalido_levanta():
    import pytest
    with pytest.raises(ValueError):
        parse_vision_json("não sei ler isso")
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar** — `vision_service.py`:

```python
import base64
import json
import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from app.core.auth import get_single_user
from app.core.config import settings
from app.models.models import (RawEvent, RawEventType, RawStatus, ScheduledOrigin,
                               ScheduledTransaction, Transport)
from app.services.insight_service import client  # AsyncOpenAI já configurado p/ OpenRouter

VISION_PROMPT = """Você lê um print de tela de app bancário brasileiro com lançamentos futuros/agendados.
Extraia TODOS os lançamentos em JSON: {"lancamentos": [{"due_date": "YYYY-MM-DD", "description": "...", "amount": -123.45}]}
Regras: amount negativo para débitos; ignore totais e propaganda; se o ano não aparecer, use o ano do contexto do mês mostrado. Responda SÓ o JSON."""


class VisionScheduled(BaseModel):
    due_date: date
    description: str
    amount: Decimal


def parse_vision_json(raw: str) -> list[VisionScheduled]:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("resposta sem JSON")
    try:
        data = json.loads(m.group(0))
        return [VisionScheduled(**item) for item in data.get("lancamentos", [])]
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"JSON inválido da visão: {e}")


async def extract_scheduled_from_image(session, image: bytes) -> int:
    user = await get_single_user(session)
    b64 = base64.b64encode(image).decode()
    resp = await client.chat.completions.create(
        model=settings.openrouter_vision_model, max_tokens=1500,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}])
    raw_text = resp.choices[0].message.content
    event = RawEvent(user_id=user.id, type=RawEventType.whatsapp_image,
                     transport=Transport.whatsapp, payload=raw_text)
    session.add(event)
    try:
        items = parse_vision_json(raw_text)
    except ValueError as e:
        event.status = RawStatus.failed
        event.error = str(e)
        await session.commit()
        raise
    created = 0
    for it in items:
        dup = (await session.execute(select(ScheduledTransaction).where(
            ScheduledTransaction.due_date == it.due_date,
            ScheduledTransaction.amount == it.amount,
            ScheduledTransaction.description == it.description))).scalar_one_or_none()
        if dup:
            continue
        session.add(ScheduledTransaction(user_id=user.id, due_date=it.due_date,
                                         description=it.description, amount=it.amount,
                                         origin=ScheduledOrigin.print_vision))
        created += 1
    await session.commit()
    return created
```

- [ ] **Step 4: Rodar testes** → 3 PASS. Validação real: rodar contra `docs/exemplos/WhatsApp Image 2026-07-04 at 10.53.09.jpeg` e conferir os 7 lançamentos (R$ 7,37 GTI, R$ 690,00 MY DOGGIE, R$ 0,05 poupança, R$ 81,90 CLARO, R$ 117,41 CELESC, R$ 365,10 Pix Ivone, R$ 436,05 HUBCARE).

- [ ] **Step 5: Commit** — `git commit -m "feat: visao para prints de lancamentos futuros"`

---

### Task 4: Cliente Inter Empresas (extrato + saldo + agendamentos)

**Files:**
- Create: `backend/app/services/inter_service.py`
- Modify: `backend/app/models/models.py` + migração Alembic: `Source.balance: Numeric(12,2) | None`, `Source.balance_date: DateTime | None`, `Source.low_balance_threshold: Numeric(12,2) default 0`
- Modify: `backend/app/main.py` (job diário 07:00)
- Modify: `backend/scripts/seed.py` (adicionar fonte `inter_pj`, `entity=empresa`)
- Test: `backend/tests/test_inter.py`

**Interfaces:**
- Produces: `InterClient` com `get_token() -> str` (OAuth2 client_credentials, mTLS `cert=(settings.inter_cert_path, settings.inter_key_path)`, cache até expirar), `get_saldo() -> Decimal`, `get_extrato(dias: int = 30) -> list[dict]`, `get_pagamentos_agendados() -> list[dict]`; `sync_inter(session) -> ImportReport` (transações `source_channel=inter`, `entity=empresa`, dedup por `idTransacao`; saldo → `Source.balance`; agendados → `ScheduledTransaction(origin=inter_agendado)`).
- Endpoints Inter (validar na doc oficial ao executar): token `POST https://cdpj.partners.bancointer.com.br/oauth/v2/token` (scopes `extrato.read pagamento-pix.write pagamento-pix.read`), extrato `GET /banking/v2/extrato/completo`, saldo `GET /banking/v2/saldo`, pagamentos agendados `GET /banking/v2/pagamento` — TODOS com mTLS.

- [ ] **Step 1: Teste falhando** — `backend/tests/test_inter.py` (API mockada):

```python
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.core.auth import get_single_user
from app.models.models import Entity, Source, SourceType, Transaction, TxChannel
from app.services.inter_service import sync_inter

EXTRATO = [{"idTransacao": "i-1", "dataEntrada": "2026-07-01", "valor": "-350.00",
            "descricao": "PIX ENVIADO FORNECEDOR X", "tipoOperacao": "D"},
           {"idTransacao": "i-2", "dataEntrada": "2026-07-02", "valor": "1200.00",
            "descricao": "PIX RECEBIDO CLIENTE Y", "tipoOperacao": "C"}]


async def test_sync_cria_transacoes_empresa(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.inter_pj, entity=Entity.empresa,
                 bank_name="Inter Empresas")
    session.add(src); await session.commit()
    with patch("app.services.inter_service.InterClient") as MockClient:
        inst = MockClient.return_value
        inst.get_extrato = AsyncMock(return_value=EXTRATO)
        inst.get_saldo = AsyncMock(return_value=Decimal("8500.00"))
        inst.get_pagamentos_agendados = AsyncMock(return_value=[])
        r = await sync_inter(session)
    assert r.novas == 2
    txs = (await session.execute(select(Transaction))).scalars().all()
    assert all(t.entity == Entity.empresa and t.source_channel == TxChannel.inter for t in txs)
    await session.refresh(src)
    assert float(src.balance) == 8500.00
    # reimport não duplica
    with patch("app.services.inter_service.InterClient") as MockClient:
        inst = MockClient.return_value
        inst.get_extrato = AsyncMock(return_value=EXTRATO)
        inst.get_saldo = AsyncMock(return_value=Decimal("8500.00"))
        inst.get_pagamentos_agendados = AsyncMock(return_value=[])
        r2 = await sync_inter(session)
    assert r2.novas == 0
```

- [ ] **Step 2: Rodar e ver falhar.** — **Step 3: Migração** dos campos de `Source` (`alembic revision --autogenerate -m "source balance"` + upgrade). — **Step 4: Implementar** `inter_service.py`:

```python
import time
from decimal import Decimal

import httpx

from app.core.auth import get_single_user
from app.core.config import settings
from app.models.models import (ScheduledOrigin, ScheduledTransaction, Source, SourceType,
                               Transaction, TxChannel, TxStatus)
from app.services.import_service import ImportReport, enrich_and_fill
from sqlalchemy import select
from datetime import datetime, timezone

BASE = "https://cdpj.partners.bancointer.com.br"


class InterClient:
    def __init__(self):
        self._token: str | None = None
        self._exp: float = 0
        self._cert = (settings.inter_cert_path, settings.inter_key_path)

    async def get_token(self) -> str:
        if self._token and time.time() < self._exp - 60:
            return self._token
        async with httpx.AsyncClient(cert=self._cert, timeout=30) as c:
            r = await c.post(f"{BASE}/oauth/v2/token", data={
                "client_id": settings.inter_client_id,
                "client_secret": settings.inter_client_secret,
                "grant_type": "client_credentials",
                "scope": "extrato.read pagamento-pix.write pagamento-pix.read"})
            r.raise_for_status()
            body = r.json()
            self._token, self._exp = body["access_token"], time.time() + body["expires_in"]
            return self._token

    async def _get(self, path: str, params: dict | None = None) -> dict:
        token = await self.get_token()
        async with httpx.AsyncClient(cert=self._cert, timeout=60) as c:
            r = await c.get(f"{BASE}{path}", params=params,
                            headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            return r.json()

    async def get_saldo(self) -> Decimal:
        return Decimal(str((await self._get("/banking/v2/saldo"))["disponivel"]))

    async def get_extrato(self, dias: int = 30) -> list[dict]:
        from datetime import date, timedelta
        fim, inicio = date.today(), date.today() - timedelta(days=dias)
        body = await self._get("/banking/v2/extrato/completo",
                               {"dataInicio": inicio.isoformat(), "dataFim": fim.isoformat()})
        return body.get("transacoes", [])

    async def get_pagamentos_agendados(self) -> list[dict]:
        body = await self._get("/banking/v2/pagamento", {"filtrarDataPor": "VENCIMENTO"})
        return [p for p in (body if isinstance(body, list) else body.get("pagamentos", []))
                if p.get("statusPagamento") == "AGENDADO"]


async def sync_inter(session) -> ImportReport:
    user = await get_single_user(session)
    src = (await session.execute(select(Source).where(
        Source.type == SourceType.inter_pj))).scalar_one_or_none()
    if src is None or not settings.inter_client_id:
        return ImportReport()
    client = InterClient()
    report = ImportReport()
    existing = {r[0] for r in await session.execute(
        select(Transaction.external_id).where(Transaction.source_id == src.id))}
    for t in await client.get_extrato():
        ext = t["idTransacao"]
        if ext in existing:
            report.duplicadas += 1
            continue
        valor = Decimal(str(t["valor"]))
        if t.get("tipoOperacao") == "D" and valor > 0:
            valor = -valor
        tx = Transaction(user_id=user.id, source_id=src.id, external_id=ext,
                         amount=valor,
                         date=datetime.fromisoformat(t["dataEntrada"]).replace(tzinfo=timezone.utc),
                         raw_description=t.get("descricao", ""),
                         source_channel=TxChannel.inter, entity=src.entity,
                         status=TxStatus.confirmada)
        await enrich_and_fill(tx)
        session.add(tx)
        existing.add(ext)
        report.novas += 1
    src.balance = await client.get_saldo()
    src.balance_date = datetime.now(timezone.utc)
    for p in await client.get_pagamentos_agendados():
        due = p.get("dataVencimento") or p.get("dataPagamento")
        desc = p.get("descricao") or p.get("beneficiario", "Pagamento agendado Inter")
        amount = -Decimal(str(p.get("valor", 0)))
        dup = (await session.execute(select(ScheduledTransaction).where(
            ScheduledTransaction.due_date == datetime.fromisoformat(due).date(),
            ScheduledTransaction.amount == amount,
            ScheduledTransaction.description == desc))).scalar_one_or_none()
        if dup is None:
            session.add(ScheduledTransaction(user_id=user.id, source_id=src.id,
                                             due_date=datetime.fromisoformat(due).date(),
                                             description=desc, amount=amount,
                                             origin=ScheduledOrigin.inter_agendado))
            report.futuros += 1
    await session.commit()
    return report
```

Job diário em `main.py`: `scheduler.add_job(run_inter_sync, CronTrigger(hour=7, minute=0))` (wrapper que abre sessão própria; falha → log + fonte degradada, sem crash).

- [ ] **Step 5: Rodar testes** → PASS. — **Step 6: Setup real** (documentar em `docs/setup-inter.md`): gerar certificado no portal Inter Empresas, colocar `.crt`/`.key` na VPS via volume, preencher `.env`, rodar sync manual (`POST /api/v1/inter/sync` — rota fina chamando `sync_inter`).

- [ ] **Step 7: Commit** — `git commit -m "feat: sync Inter Empresas com saldo e agendamentos"`

---

### Task 5: Projeção de saldo + sugestões de transferência

**Files:**
- Create: `backend/app/services/projection_service.py`
- Create: `backend/app/api/v1/endpoints/scheduled.py` (estender o do R1a Task 14 com `/projection` e reconciliação)
- Modify: `backend/app/main.py` (job diário 07:30, após o sync Inter)
- Test: `backend/tests/test_projection.py`

**Interfaces:**
- Produces:
  - `compute_projection(session, days: int = 30) -> dict` → `{source_id: [{date, saldo_projetado}]}` — parte de `Source.balance` (fontes pessoais: saldo derivado do último OFX pode ser nulo → projeta só o delta dos futuros com aviso `saldo_base_desconhecido: true`)
  - `detect_low_balance(session) -> list[TransferSuggestion]` — cria sugestão quando projeção de fonte `pessoal` cruza `low_balance_threshold` E existe fonte `empresa` com `balance` suficiente; texto do motivo cita data e causas (descrições dos futuros); dedup: não recriar sugestão `sugerida` aberta para a mesma semana
  - `reconcile_scheduled(session)` — `previsto` + transação real com mesmo valor (±R$ 0,01) e data ±2 dias → `efetivado` (chamar ao final de todo import — adicionar chamada em `import_ofx`/`import_fatura`/`sync_inter`)
  - `GET /api/v1/scheduled/projection?days=30`; `run_projection_job()` = reconcile + detect + push da sugestão

- [ ] **Step 1: Testes falhando** — `backend/tests/test_projection.py`:

```python
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.auth import get_single_user
from app.models.models import (Entity, ScheduledOrigin, ScheduledStatus, ScheduledTransaction,
                               Source, SourceType, Transaction, TransferSuggestion,
                               TxChannel, TxStatus)
from app.services.projection_service import compute_projection, detect_low_balance, reconcile_scheduled


async def _setup(session):
    user = await get_single_user(session)
    bb = Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal,
                bank_name="BB", balance=Decimal("300.00"),
                balance_date=datetime.now(timezone.utc), low_balance_threshold=Decimal("0"))
    inter = Source(user_id=user.id, type=SourceType.inter_pj, entity=Entity.empresa,
                   bank_name="Inter", balance=Decimal("5000.00"),
                   balance_date=datetime.now(timezone.utc))
    session.add_all([bb, inter]); await session.flush()
    session.add(ScheduledTransaction(user_id=user.id, source_id=bb.id,
                                     due_date=date.today() + timedelta(days=5),
                                     description="PAG BOLETO GRANDE", amount=Decimal("-500.00"),
                                     origin=ScheduledOrigin.ofx_futuro))
    await session.commit()
    return user, bb, inter


async def test_projecao_fica_negativa(session):
    user, bb, inter = await _setup(session)
    proj = await compute_projection(session, days=10)
    series = proj[str(bb.id)]
    assert any(p["saldo_projetado"] < 0 for p in series)


async def test_sugestao_criada_uma_vez(session):
    await _setup(session)
    s1 = await detect_low_balance(session)
    assert len(s1) == 1 and "PAG BOLETO GRANDE" in s1[0].reason
    s2 = await detect_low_balance(session)
    assert len(s2) == 0  # dedup da sugestão aberta


async def test_reconcile_marca_efetivado(session):
    user, bb, inter = await _setup(session)
    session.add(Transaction(user_id=user.id, source_id=bb.id, external_id="r-1",
                            amount=Decimal("-500.00"),
                            date=datetime.now(timezone.utc) + timedelta(days=5),
                            raw_description="PAG BOLETO GRANDE",
                            source_channel=TxChannel.ofx, entity=Entity.pessoal,
                            status=TxStatus.confirmada))
    await session.commit()
    await reconcile_scheduled(session)
    st = (await session.execute(select(ScheduledTransaction))).scalar_one()
    assert st.status == ScheduledStatus.efetivado
```

- [ ] **Step 2: Rodar e ver falhar.** — **Step 3: Implementar** `projection_service.py`: `compute_projection` agrupa `scheduled_transactions(status=previsto)` por fonte e acumula dia a dia a partir de `Source.balance` (ou 0 com flag); `detect_low_balance` acha o primeiro dia negativo de fonte pessoal, calcula `valor = abs(min_saldo) arredondado para cima em múltiplos de R$ 100`, verifica `TransferSuggestion.status == "sugerida"` aberta (dedup), cria com `reason` citando data e até 3 descrições de futuros, e retorna as novas; `run_projection_job` chama `reconcile_scheduled` → `detect_low_balance` → para cada nova sugestão `send_push(session, "Saldo baixo previsto", reason)`. `GET /scheduled/projection` retorna `compute_projection`.

- [ ] **Step 4: Rodar testes** → 3 PASS. **Step 5: Commit** — `git commit -m "feat: projecao de saldo e sugestoes de transferencia"`

---

### Task 6: Execução de transferência (Pix Inter) com confirmação

**Files:**
- Create: `backend/app/api/v1/endpoints/transfers.py`
- Modify: `backend/app/services/inter_service.py` (método `send_pix`)
- Test: `backend/tests/test_transfers.py`

**Interfaces:**
- Produces: `InterClient.send_pix(valor: Decimal, chave_destino: str, descricao: str) -> str` (retorna id/e2e do Pix; endpoint `POST /banking/v2/pix` — validar na doc oficial); rotas `GET /api/v1/transfers?status=sugerida`, `POST /api/v1/transfers/{id}/confirm` body `{"amount": "500.00"}` (usa `settings.inter_pix_dest_key` como destino; muda status `sugerida→executada`, grava `pix_id`; erro da API → status permanece `sugerida`, resposta 502 com mensagem legível), `POST /api/v1/transfers/{id}/dismiss` (→ `recusada`).

- [ ] **Step 1: Testes falhando** — `backend/tests/test_transfers.py`:

```python
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.core.auth import get_single_user
from app.models.models import TransferSuggestion


async def _sugestao(session):
    user = await get_single_user(session)
    s = TransferSuggestion(user_id=user.id, amount=Decimal("500.00"),
                           reason="Saldo BB ficará -R$ 200 em 16/07")
    session.add(s); await session.commit()
    return s


async def test_confirmar_executa_pix(client, session):
    s = await _sugestao(session)
    with patch("app.api.v1.endpoints.transfers.InterClient") as MC:
        MC.return_value.send_pix = AsyncMock(return_value="E2E123")
        r = await client.post(f"/api/v1/transfers/{s.id}/confirm", json={"amount": "450.00"})
    assert r.status_code == 200
    await session.refresh(s)
    assert s.status == "executada" and s.pix_id == "E2E123"


async def test_falha_da_api_mantem_sugerida(client, session):
    s = await _sugestao(session)
    with patch("app.api.v1.endpoints.transfers.InterClient") as MC:
        MC.return_value.send_pix = AsyncMock(side_effect=RuntimeError("api fora"))
        r = await client.post(f"/api/v1/transfers/{s.id}/confirm", json={"amount": "450.00"})
    assert r.status_code == 502
    await session.refresh(s)
    assert s.status == "sugerida"


async def test_dismiss(client, session):
    s = await _sugestao(session)
    r = await client.post(f"/api/v1/transfers/{s.id}/dismiss")
    assert r.status_code == 200
    await session.refresh(s)
    assert s.status == "recusada"
```

- [ ] **Step 2: Rodar e ver falhar.** — **Step 3: Implementar.** `send_pix`:

```python
    async def send_pix(self, valor: Decimal, chave_destino: str, descricao: str) -> str:
        token = await self.get_token()
        async with httpx.AsyncClient(cert=self._cert, timeout=60) as c:
            r = await c.post(f"{BASE}/banking/v2/pix",
                             headers={"Authorization": f"Bearer {token}"},
                             json={"valor": str(valor), "descricao": descricao[:60],
                                   "destinatario": {"tipo": "CHAVE", "chave": chave_destino}})
            r.raise_for_status()
            body = r.json()
            return body.get("endToEndId") or body.get("codigoSolicitacao", "")
```

`endpoints/transfers.py` conforme interface (validações: sugestão existe e está `sugerida`; `amount > 0` e `<= 5000` como teto sanidade hardcoded com comentário).

- [ ] **Step 4: Rodar testes** → 3 PASS. **Step 5: Commit** — `git commit -m "feat: transferencia pix inter com confirmacao explicita"`

---

### Task 7: Front — Futuros completo (projeção + sugestões) e entidade Empresa

**Files:**
- Modify: `frontend/src/pages/Futuros.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Config.tsx`

- [ ] **Step 1: Futuros.tsx** — gráfico de linha Recharts com `GET /scheduled/projection` (uma linha por fonte, linha de zero destacada); lista de futuros por data com badge da origem (extrato/print/Inter/fatura); seção "Sugestões": cards de `GET /transfers?status=sugerida` com motivo, valor editável, botões **[Confirmar Pix]** (→ modal de confirmação mostrando valor/destino → `POST /confirm`; sucesso mostra e2e id) e **[Dispensar]**. Erro 502 → mensagem "Pix falhou — faça manualmente no app do Inter" sem remover o card.
- [ ] **Step 2: Dashboard.tsx** — seletor de entidade já existente do R1a passa a ter dados reais de `empresa` (nenhuma mudança de código além de garantir que `empresa` aparece quando houver fonte).
- [ ] **Step 3: Config.tsx** — seção Inter: status do certificado (dias p/ expirar — campo novo `GET /sources` já expõe), último sync, botão "Sincronizar agora" (`POST /inter/sync`); seção WhatsApp: instruções de configuração do webhook + teste ("envie um OFX para si mesmo").
- [ ] **Step 4: Verificar** com backend local (Inter mockado) e `npx tsc --noEmit`. **Step 5: Commit** — `git commit -m "feat: tela futuros com projecao e confirmacao de transferencia"`

---

### Task 8: Aceitação real R1b

- [ ] **Step 1:** Webhook configurado na Evolution real → enviar OFX real pelo WhatsApp → resposta com contagens chega no chat.
- [ ] **Step 2:** Enviar print real da tela Futuros do BB → 7 lançamentos aparecem em Futuros.
- [ ] **Step 3:** Certificado Inter gerado, sync real → transações da empresa no dashboard (entidade Empresa), saldo visível.
- [ ] **Step 4:** Forçar cenário de saldo baixo (threshold alto temporário) → push de sugestão chega → **transferência real de R$ 1,00** confirmada no app → Pix cai na conta pessoal → sugestão `executada` com e2e id.
- [ ] **Step 5:** Reverter threshold; commit final — `git commit -m "chore: aceitacao R1b concluida"`.

---

## Cobertura da spec (self-review)

| Spec § | Task |
|---|---|
| §4.5 Inter (extrato, saldo, agendados, mTLS, invest. indisponível) | 4 |
| §4.6 WhatsApp (roteamento, allowlist, respostas) | 1, 2 |
| §6 visão para prints | 3 |
| §7 futuros, projeção, sugestão, Pix confirmado, efetivação | 5, 6, 7 |
| §8 telas (Futuros completo, Config Inter/WhatsApp) | 7 |
| §9 erros (cert expirado, Pix falha, remetente estranho) | 1, 4, 6 |
| §10 aceitação real (R$ 1,00) | 8 |
