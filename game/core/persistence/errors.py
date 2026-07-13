"""持久化基础设施的稳定异常边界。"""


class PersistenceError(Exception):
    """所有持久化基础设施错误的基类。"""


class SchemaVersionError(PersistenceError):
    """数据库不是当前结构版本。"""


class AggregateNotFound(PersistenceError):
    """需要的聚合快照不存在。"""


class ConcurrencyConflict(PersistenceError):
    """条件更新没有命中预期 revision。"""


class TransactionMismatch(PersistenceError):
    """同一事务 ID 对应了不同内容指纹。"""


class CorruptPersistenceData(PersistenceError):
    """数据库中的结构化数据无法通过当前模型校验。"""


class ContentActivationMismatch(PersistenceError):
    """数据库激活的内容指纹与当前运行期不一致。"""


__all__ = [
    "AggregateNotFound",
    "ConcurrencyConflict",
    "ContentActivationMismatch",
    "CorruptPersistenceData",
    "PersistenceError",
    "SchemaVersionError",
    "TransactionMismatch",
]
