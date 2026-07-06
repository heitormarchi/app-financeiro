from datetime import date

from sqlalchemy import select

from app.models.models import RecurrenceFrequency, RecurringRule, ScheduledOrigin, ScheduledTransaction
from app.services.date_utils import add_months, clamp_day


def _occurrences(rule: RecurringRule, start: date, end: date) -> list[date]:
    occs = []
    if rule.frequency == RecurrenceFrequency.anual:
        for y in range(start.year, end.year + 1):
            d = clamp_day(y, rule.month, rule.day)
            if start <= d <= end and d >= rule.start_date:
                occs.append(d)
    else:
        y, m = start.year, start.month
        while True:
            d = clamp_day(y, m, rule.day)
            if d > end:
                break
            if d >= start and d >= rule.start_date:
                occs.append(d)
            m += 1
            if m == 13:
                m, y = 1, y + 1
    return occs


async def materialize_recurring(session, months_horizon: int = 12) -> list[ScheduledTransaction]:
    rules = (await session.execute(select(RecurringRule).where(
        RecurringRule.active.is_(True)))).scalars().all()
    today = date.today()
    horizon_end = add_months(today, months_horizon)
    created: list[ScheduledTransaction] = []
    for rule in rules:
        for occ_date in _occurrences(rule, today, horizon_end):
            exists = (await session.execute(select(ScheduledTransaction).where(
                ScheduledTransaction.recurring_rule_id == rule.id,
                ScheduledTransaction.due_date == occ_date,
            ))).scalars().first()
            if exists:
                continue
            st = ScheduledTransaction(
                user_id=rule.user_id, source_id=rule.source_id, due_date=occ_date,
                description=rule.description, amount=rule.amount,
                origin=ScheduledOrigin.manual, recurring_rule_id=rule.id,
            )
            session.add(st)
            created.append(st)
    await session.commit()
    return created
