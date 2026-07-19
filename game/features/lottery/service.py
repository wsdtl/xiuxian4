"""彩票玩法：购票、环形开奖和中央资金原子结算。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
import secrets

from game.content.catalog.economy import (
    LOTTERY_MIN_PRIZE,
    LOTTERY_TICKET_PRICE,
)
from game.content.catalog.foundation import PRIMARY_CURRENCY_ID
from game.core.gameplay import (
    FundAllocation,
    LedgerAccount,
    LedgerAccountKind,
    LedgerEngine,
    LedgerState,
    LedgerTransaction,
    OpenLedgerAccount,
    SplitFunds,
    TransferFunds,
    RuleContext,
    Ruleset,
    SeededRandomSource,
)
from game.rules.character import PRIMARY_LEDGER_ID
from game.rules.economy import PRIMARY_TAX_ACCOUNT_ID, PRIMARY_TAX_OWNER_ID
from game.rules.lottery import (
    DRAW_MIN_PARTICIPANTS,
    DRAW_POOL_MAX,
    LOTTERY_RULESET_VERSION,
    LotteryRound,
    LotteryState,
    LotteryTicket,
    LotteryWinner,
    circular_distance,
    due_round_day,
    pool_breakdown,
    prize_tiers,
    round_draw_at,
    signup_round_day,
)

from .models import LotteryPlayerView


LOTTERY_AGGREGATE = "snapshot.lottery"
LOTTERY_SCOPE_ID = "lottery.primary"


@dataclass(frozen=True)
class LotteryStorageKinds:
    lottery: str
    ledger: str


class LotteryFeature:
    """购票资金进入中央池，开奖只消费真实余额，不发行新货币。"""

    def __init__(
        self,
        database,
        snapshots,
        ledger_engine: LedgerEngine,
        *,
        storage,
        timezone: str,
    ) -> None:
        self.database = database
        self.snapshots = snapshots
        self.ledger_engine = ledger_engine
        self.storage = storage
        self.timezone = timezone

    def initialize(self, *, logical_time: datetime) -> LotteryState:
        with self.database.unit_of_work() as uow:
            current = self.snapshots.load(
                uow,
                self.storage.lottery,
                LOTTERY_SCOPE_ID,
                LotteryState,
            )
            if current is None:
                current = LotteryState()
                self.snapshots.insert(
                    uow,
                    self.storage.lottery,
                    LOTTERY_SCOPE_ID,
                    current,
                    logical_time,
                )
            uow.commit()
        return current

    def status(self, character_id: str, *, logical_time: datetime) -> LotteryPlayerView:
        with self.database.unit_of_work(write=False) as uow:
            state = self._state(uow)
            ledger = self.snapshots.require(
                uow,
                self.storage.ledger,
                PRIMARY_LEDGER_ID,
                LedgerState,
            )
        signup_day = signup_round_day(logical_time, self.timezone)
        due_day = due_round_day(logical_time, self.timezone)
        current = state.rounds.get(signup_day)
        due = state.rounds.get(due_day)
        return LotteryPlayerView(
            signup_day,
            current,
            current.tickets.get(character_id) if current else None,
            due,
            due.tickets.get(character_id) if due else None,
            next(
                (
                    value
                    for value in due.winners
                    if value.character_id == character_id
                ),
                None,
            )
            if due
            else None,
            ledger.accounts.get(PRIMARY_TAX_ACCOUNT_ID).balance
            if ledger.accounts.get(PRIMARY_TAX_ACCOUNT_ID)
            else 0,
        )

    def purchase(
        self,
        character_id: str,
        character_name: str,
        number: str,
        *,
        logical_time: datetime,
    ) -> str:
        number = str(number or "").strip()
        if len(number) != 6 or not number.isdigit():
            raise ValueError("彩票号码必须是 000000 到 999999 的六位数字")
        round_day = signup_round_day(logical_time, self.timezone)
        with self.database.unit_of_work() as uow:
            state = self._state(uow)
            current = state.rounds.get(round_day, LotteryRound(round_day))
            owned = tuple(
                value
                for value in current.tickets.values()
                if value.character_id == character_id
            )
            if owned:
                return f"本期已经购买彩票：{owned[0].number}，不能追加或更换。"
            if any(ticket.number == number for ticket in current.tickets.values()):
                raise ValueError(f"号码 {number} 已被购买，请更换")
            ledger = self.snapshots.require(
                uow,
                self.storage.ledger,
                PRIMARY_LEDGER_ID,
                LedgerState,
            )
            wallet = _wallet(ledger, character_id)
            tax = ledger.accounts.get(PRIMARY_TAX_ACCOUNT_ID)
            operations: list[object] = []
            expected = {wallet.id: wallet.revision}
            if tax is None:
                tax = LedgerAccount(
                    PRIMARY_TAX_ACCOUNT_ID,
                    "owner.tax_authority",
                    PRIMARY_TAX_OWNER_ID,
                    PRIMARY_CURRENCY_ID,
                )
                operations.append(OpenLedgerAccount(tax))
            else:
                expected[tax.id] = tax.revision
            operations.append(
                TransferFunds(
                    wallet.id,
                    tax.id,
                    LOTTERY_TICKET_PRICE,
                )
            )
            ledger_outcome = self.ledger_engine.execute(
                LedgerTransaction(
                    f"lottery:purchase:{round_day}:{character_id}:{number}",
                    character_id,
                    "economy.lottery_ticket_purchase",
                    tuple(operations),
                    expected_revisions=expected,
                    metadata={"round_day": round_day, "number": number},
                ),
                state=ledger,
                context=_context(
                    f"purchase:{round_day}:{character_id}:{number}",
                    logical_time,
                ),
            )
            if ledger_outcome.failure or ledger_outcome.value is None:
                raise ValueError(
                    ledger_outcome.failure.message
                    if ledger_outcome.failure
                    else "购票付款失败"
                )
            tickets = dict(current.tickets)
            ticket = LotteryTicket(character_id, character_name, number)
            tickets[character_id] = ticket
            updated_round = replace(current, tickets=tickets)
            rounds = dict(state.rounds)
            rounds[round_day] = updated_round
            updated = replace(state, rounds=rounds, revision=state.revision + 1)
            self.snapshots.update(
                uow,
                self.storage.lottery,
                LOTTERY_SCOPE_ID,
                state,
                updated,
                logical_time,
            )
            self.snapshots.update(
                uow,
                self.storage.ledger,
                PRIMARY_LEDGER_ID,
                ledger,
                ledger_outcome.value.state,
                logical_time,
            )
            uow.commit()
        return (
            f"已购买第 {round_day} 期彩票：{number} | "
            f"支付 {LOTTERY_TICKET_PRICE}"
        )

    def winner_history(
        self,
        character_id: str,
        *,
        limit: int = 10,
    ) -> tuple[tuple[str, LotteryWinner], ...]:
        with self.database.unit_of_work(write=False) as uow:
            state = self._state(uow)
        values = [
            (round_value.round_day, winner)
            for round_value in state.rounds.values()
            for winner in round_value.winners
            if winner.character_id == character_id
        ]
        values.sort(key=lambda value: value[0], reverse=True)
        return tuple(values[: max(1, int(limit))])

    def draw_due(self, *, logical_time: datetime, max_rounds: int = 7) -> tuple[str, ...]:
        """后台补开奖；玩家命令不直接触发开奖。"""

        completed: list[str] = []
        for _ in range(max(1, int(max_rounds))):
            with self.database.unit_of_work(write=False) as uow:
                state = self._state(uow)
                pending = sorted(
                    (
                        value
                        for value in state.rounds.values()
                        if value.status == "pending"
                        and round_draw_at(value.round_day, self.timezone) <= logical_time
                    ),
                    key=lambda value: value.round_day,
                )
            if not pending:
                break
            round_day = pending[0].round_day
            summary = self._draw_round(round_day, logical_time)
            completed.append(summary)
            if summary.endswith("中央资金不足，等待补开"):
                break
        return tuple(completed)

    def _draw_round(self, round_day: str, logical_time: datetime) -> str:
        with self.database.unit_of_work() as uow:
            state = self._state(uow)
            current = state.rounds.get(round_day)
            if current is None or current.status != "pending":
                return f"{round_day}: 已处理"
            if not current.tickets:
                self._save_round(
                    uow,
                    state,
                    replace(current, status="skipped", reason="无人购票"),
                    logical_time,
                )
                uow.commit()
                return f"{round_day}: 无人购票"
            ledger = self.snapshots.require(
                uow,
                self.storage.ledger,
                PRIMARY_LEDGER_ID,
                LedgerState,
            )
            tax = ledger.accounts.get(PRIMARY_TAX_ACCOUNT_ID)
            available_balance = (
                ledger.available_balance(tax.id, logical_time=logical_time)
                if tax is not None
                else 0
            )
            if len(current.tickets) < DRAW_MIN_PARTICIPANTS:
                if tax is None:
                    return f"{round_day}: 中央资金不足，等待补开"
                return self._refund_underfilled_round(
                    uow,
                    state,
                    current,
                    ledger,
                    tax,
                    logical_time,
                )
            base_pool, subsidy, pool = pool_breakdown(
                available_balance,
                len(current.tickets),
            )
            if tax is None or available_balance < min(base_pool, DRAW_POOL_MAX):
                return f"{round_day}: 中央资金不足，等待补开"
            winning_number = f"{secrets.randbelow(1_000_000):06d}"
            ranked = sorted(
                current.tickets.values(),
                key=lambda ticket: (
                    circular_distance(ticket.number, winning_number),
                    sha256(
                        f"{round_day}|{ticket.character_id}|{ticket.number}|{winning_number}".encode()
                    ).hexdigest(),
                ),
            )
            winners: list[LotteryWinner] = []
            allocation_amounts: dict[str, int] = {}
            cursor = 0
            wallets = {
                account.owner_id: account
                for account in ledger.accounts.values()
                if account.kind is LedgerAccountKind.STANDARD
                and account.owner_kind == "owner.character"
                and account.currency_id == PRIMARY_CURRENCY_ID
            }
            tiers = prize_tiers(len(ranked))
            allocated_pool = 0
            for tier_index, (tier, count, rate) in enumerate(tiers):
                rank_start = cursor + 1
                selected = ranked[cursor : cursor + count]
                cursor += len(selected)
                if not selected:
                    continue
                tier_pool = (
                    pool - allocated_pool
                    if tier_index == len(tiers) - 1
                    else int(pool * rate)
                )
                allocated_pool += tier_pool
                amount, remainder = divmod(tier_pool, len(selected))
                for offset, ticket in enumerate(selected):
                    winner_amount = amount + (1 if offset < remainder else 0)
                    if winner_amount < LOTTERY_MIN_PRIZE:
                        continue
                    wallet = wallets.get(ticket.character_id)
                    if wallet is None:
                        raise RuntimeError(f"中奖角色缺少主货币钱包：{ticket.character_id}")
                    distance = circular_distance(ticket.number, winning_number)
                    winners.append(
                        LotteryWinner(
                            ticket.character_id,
                            ticket.character_name,
                            ticket.number,
                            tier,
                            rank_start + offset,
                            distance,
                            winner_amount,
                        )
                    )
                    allocation_amounts[wallet.id] = (
                        allocation_amounts.get(wallet.id, 0) + winner_amount
                    )
            allocations = [
                FundAllocation(account_id, amount)
                for account_id, amount in sorted(allocation_amounts.items())
            ]
            next_ledger = ledger
            total = sum(value.amount for value in allocations)
            if allocations:
                outcome = self.ledger_engine.execute(
                    LedgerTransaction(
                        f"lottery:{round_day}",
                        "system.lottery",
                        "economy.lottery_payout",
                        (SplitFunds(tax.id, tuple(allocations)),),
                        expected_revisions={
                            tax.id: tax.revision,
                            **{
                                value.destination_account_id: ledger.accounts[
                                    value.destination_account_id
                                ].revision
                                for value in allocations
                            },
                        },
                        metadata={
                            "round_day": round_day,
                            "winning_number": winning_number,
                            "base_pool": base_pool,
                            "central_subsidy": subsidy,
                        },
                    ),
                    state=ledger,
                    context=_context(round_day, logical_time),
                )
                if outcome.failure or outcome.value is None:
                    raise RuntimeError(outcome.failure.message if outcome.failure else "彩票奖金入账失败")
                next_ledger = outcome.value.state
            updated_round = replace(
                current,
                status="opened",
                winning_number=winning_number,
                pool_amount=pool,
                payout_amount=total,
                winners=tuple(winners),
            )
            self._save_round(uow, state, updated_round, logical_time)
            if next_ledger is not ledger:
                self.snapshots.update(
                    uow,
                    self.storage.ledger,
                    PRIMARY_LEDGER_ID,
                    ledger,
                    next_ledger,
                    logical_time,
                )
            uow.commit()
            return f"{round_day}: {len(current.tickets)} 张，支出 {total}"

    def _refund_underfilled_round(
        self,
        uow,
        state: LotteryState,
        current: LotteryRound,
        ledger: LedgerState,
        tax: LedgerAccount,
        logical_time: datetime,
    ) -> str:
        """截止时不足两人则原路退票，避免无法加入的轮次永久待开奖。"""

        wallets = {
            account.owner_id: account
            for account in ledger.accounts.values()
            if account.kind is LedgerAccountKind.STANDARD
            and account.owner_kind == "owner.character"
            and account.currency_id == PRIMARY_CURRENCY_ID
        }
        operations: list[TransferFunds] = []
        expected = {tax.id: tax.revision}
        for ticket in current.tickets.values():
            wallet = wallets.get(ticket.character_id)
            if wallet is None:
                raise RuntimeError(f"退票角色缺少主货币钱包：{ticket.character_id}")
            operations.append(
                TransferFunds(tax.id, wallet.id, LOTTERY_TICKET_PRICE)
            )
            expected[wallet.id] = wallet.revision
        refund_amount = len(operations) * LOTTERY_TICKET_PRICE
        if ledger.available_balance(tax.id, logical_time=logical_time) < refund_amount:
            return f"{current.round_day}: 中央资金不足，等待补开"
        outcome = self.ledger_engine.execute(
            LedgerTransaction(
                f"lottery:refund:{current.round_day}",
                "system.lottery",
                "economy.lottery_ticket_refund",
                tuple(operations),
                expected_revisions=expected,
                metadata={"round_day": current.round_day, "ticket_count": len(operations)},
            ),
            state=ledger,
            context=_context(f"refund:{current.round_day}", logical_time),
        )
        if outcome.failure or outcome.value is None:
            raise RuntimeError(outcome.failure.message if outcome.failure else "彩票退票失败")
        updated_round = replace(
            current,
            status="skipped",
            reason="参与不足，票款已退回",
        )
        self._save_round(uow, state, updated_round, logical_time)
        self.snapshots.update(
            uow,
            self.storage.ledger,
            PRIMARY_LEDGER_ID,
            ledger,
            outcome.value.state,
            logical_time,
        )
        uow.commit()
        return f"{current.round_day}: 参与不足，已退回 {refund_amount}"

    def _state(self, uow) -> LotteryState:
        return self.snapshots.require(
            uow,
            self.storage.lottery,
            LOTTERY_SCOPE_ID,
            LotteryState,
        )

    def _save_round(self, uow, state, round_value, logical_time) -> None:
        rounds = dict(state.rounds)
        rounds[round_value.round_day] = round_value
        updated = replace(state, rounds=rounds, revision=state.revision + 1)
        self.snapshots.update(
            uow,
            self.storage.lottery,
            LOTTERY_SCOPE_ID,
            state,
            updated,
            logical_time,
        )


def _wallet(ledger: LedgerState, character_id: str):
    try:
        return next(
            account
            for account in ledger.accounts.values()
            if account.kind is LedgerAccountKind.STANDARD
            and account.owner_kind == "owner.character"
            and account.owner_id == character_id
            and account.currency_id == PRIMARY_CURRENCY_ID
        )
    except StopIteration as exc:
        raise ValueError("当前角色缺少主货币钱包") from exc


def _context(trace_id: str, logical_time: datetime) -> RuleContext:
    return RuleContext(
        f"lottery:{trace_id}",
        LOTTERY_RULESET_VERSION,
        Ruleset("ruleset.lottery"),
        logical_time,
        SeededRandomSource(trace_id),
    )


__all__ = ["LOTTERY_AGGREGATE", "LOTTERY_SCOPE_ID", "LotteryFeature", "LotteryStorageKinds"]
