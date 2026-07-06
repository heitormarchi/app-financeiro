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
