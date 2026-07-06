import asyncio

from app.core.auth import get_single_user
from app.core.database import AsyncSessionLocal
from app.models.models import Entity, Source, SourceType


async def main():
    async with AsyncSessionLocal() as session:
        user = await get_single_user(session)
        for t, name in [
            (SourceType.bb_conta, "BB Conta Corrente"),
            (SourceType.caixa_conta, "Caixa Conta Corrente"),
            (SourceType.caixa_cartao, "Cartão de Crédito Caixa"),
        ]:
            session.add(Source(user_id=user.id, type=t, entity=Entity.pessoal, bank_name=name))
        session.add(Source(user_id=user.id, type=SourceType.inter_pj, entity=Entity.empresa,
                           bank_name="Inter Empresas"))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
