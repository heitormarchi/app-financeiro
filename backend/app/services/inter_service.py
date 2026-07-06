import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.core.auth import get_single_user
from app.core.config import settings
from app.models.models import (ScheduledOrigin, ScheduledTransaction, Source, SourceType,
                               Transaction, TxChannel, TxStatus)
from app.services.import_service import ImportReport, enrich_and_fill

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


async def sync_inter(session) -> ImportReport:
    user = await get_single_user(session)
    src = (await session.execute(select(Source).where(
        Source.type == SourceType.inter_pj))).scalar_one_or_none()
    if src is None:
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
