"""正式游戏操作共享的确定性规则上下文。"""

from datetime import datetime

from game.core.gameplay import RuleContext, Ruleset, SeededRandomSource


GAME_OPERATION_RULE_VERSION = "rules.game_operation_v1"


def game_operation_context(
    trace_id: str,
    *,
    logical_time: datetime,
) -> RuleContext:
    """用稳定事务身份构造可重放、可回滚的规则上下文。"""

    normalized_trace = str(trace_id or "").strip()
    if not normalized_trace:
        raise ValueError("游戏操作缺少 trace_id")
    return RuleContext(
        normalized_trace,
        GAME_OPERATION_RULE_VERSION,
        Ruleset("ruleset.standard"),
        logical_time,
        SeededRandomSource(normalized_trace),
    )


__all__ = ["GAME_OPERATION_RULE_VERSION", "game_operation_context"]
