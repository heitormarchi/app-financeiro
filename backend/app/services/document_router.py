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
    return SourceType.caixa_conta if "CAIXA" in head else SourceType.bb_conta


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
