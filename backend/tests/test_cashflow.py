from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.auth import get_single_user
from app.models.models import (Entity, ScheduledOrigin, ScheduledTransaction, Source, SourceType,
                               Transaction, TxChannel, TxStatus)
from app.services.date_utils import add_months
from app.services.projection_service import compute_monthly_cashflow, project_future_installments


async def test_projeta_parcelas_restantes(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.caixa_cartao, entity=Entity.pessoal, bank_name="Caixa")
    session.add(src); await session.flush()
    hoje = datetime.now(timezone.utc)
    session.add(Transaction(
        user_id=user.id, source_id=src.id, external_id="fat-1", amount=Decimal("-150.00"),
        date=hoje, raw_description="LOJA MODA EXEMPLO", merchant="Loja Moda Exemplo",
        source_channel=TxChannel.pdf, entity=Entity.pessoal, status=TxStatus.confirmada,
        installment_no=4, installment_total=7, original_purchase_date=date(2026, 4, 28),
    ))
    await session.commit()

    parcelas = await project_future_installments(session)
    assert len(parcelas) == 1
    item = parcelas[0]
    assert item["installment_no_atual"] == 4
    assert item["installment_total"] == 7
    assert len(item["parcelas_restantes"]) == 3  # parcelas 5, 6, 7
    assert item["parcelas_restantes"][0]["numero"] == 5
    assert all(p["valor"] == 150.00 for p in item["parcelas_restantes"])


async def test_parcela_quitada_nao_aparece(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.caixa_cartao, entity=Entity.pessoal, bank_name="Caixa")
    session.add(src); await session.flush()
    session.add(Transaction(
        user_id=user.id, source_id=src.id, external_id="fat-2", amount=Decimal("-90.00"),
        date=datetime.now(timezone.utc), raw_description="FARMACIA EXEMPLO",
        source_channel=TxChannel.pdf, entity=Entity.pessoal, status=TxStatus.confirmada,
        installment_no=4, installment_total=4, original_purchase_date=date(2026, 3, 19),
    ))
    await session.commit()
    assert await project_future_installments(session) == []


async def test_cashflow_agrega_scheduled_nao_fatura_e_parcelas(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.caixa_cartao, entity=Entity.pessoal, bank_name="Caixa")
    session.add(src); await session.flush()
    proximo_mes = add_months(date.today(), 1)
    session.add(ScheduledTransaction(
        user_id=user.id, source_id=src.id, due_date=proximo_mes,
        description="Aluguel", amount=Decimal("-500.00"), origin=ScheduledOrigin.ofx_futuro))
    session.add(Transaction(
        user_id=user.id, source_id=src.id, external_id="fat-3", amount=Decimal("-100.00"),
        date=datetime.now(timezone.utc), raw_description="LOJA CINCO EXEMPLO",
        source_channel=TxChannel.pdf, entity=Entity.pessoal, status=TxStatus.confirmada,
        installment_no=1, installment_total=6, original_purchase_date=date.today(),
    ))
    await session.commit()

    fluxo = await compute_monthly_cashflow(session, months=3)
    bucket = next(f for f in fluxo if f["month"] == proximo_mes.strftime("%Y-%m"))
    assert bucket["total"] == -600.00  # -500 do aluguel (ofx_futuro) - 100 da parcela 2/6


async def test_cashflow_ignora_fatura_a_vencer_para_nao_duplicar_parcelas(session):
    """A fatura_a_vencer é um agregado único que a própria fatura já informa (todas as
    parcelas futuras somadas) — se o cashflow também somasse project_future_installments
    por cima, a mesma dívida contaria duas vezes. Ver relato do Heitor: "fatura e o
    detalhamento" duplicando o fluxo de caixa negativo."""
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.caixa_cartao, entity=Entity.pessoal, bank_name="Caixa")
    session.add(src); await session.flush()
    proximo_mes = add_months(date.today(), 1)
    session.add(ScheduledTransaction(
        user_id=user.id, source_id=src.id, due_date=proximo_mes,
        description="Fatura Caixa (despesas a vencer)", amount=Decimal("-5216.65"),
        origin=ScheduledOrigin.fatura_a_vencer))
    session.add(Transaction(
        user_id=user.id, source_id=src.id, external_id="fat-4", amount=Decimal("-100.00"),
        date=datetime.now(timezone.utc), raw_description="LOJA CINCO EXEMPLO",
        source_channel=TxChannel.pdf, entity=Entity.pessoal, status=TxStatus.confirmada,
        installment_no=1, installment_total=6, original_purchase_date=date.today(),
    ))
    await session.commit()

    fluxo = await compute_monthly_cashflow(session, months=3)
    bucket = next(f for f in fluxo if f["month"] == proximo_mes.strftime("%Y-%m"))
    assert bucket["total"] == -100.00  # só a parcela 2/6 — a fatura_a_vencer é ignorada
