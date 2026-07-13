"""组织成员、社会请求和主体关系的通用模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from ..events import RuleEvent
from ..ids import StableId, stable_id
from ..registry import DefinitionRegistry


MANAGE_MEMBERS_PERMISSION = "organization_permission.manage_members"
MANAGE_ROLES_PERMISSION = "organization_permission.manage_roles"
DISSOLVE_PERMISSION = "organization_permission.dissolve"


class OrganizationStatus(str, Enum):
    ACTIVE = "active"
    DISSOLVED = "dissolved"


class SocialRequestStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RelationOverflowPolicy(str, Enum):
    REJECT = "reject"
    CLAMP = "clamp"


@dataclass(frozen=True)
class OrganizationRoleDefinition:
    id: StableId
    rank: int
    permissions: frozenset[StableId] = frozenset()
    maximum_members: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="organization role id"))
        permissions = frozenset(
            stable_id(value, field="organization permission id") for value in self.permissions
        )
        if self.rank < 0 or (self.maximum_members is not None and self.maximum_members < 1):
            raise ValueError("组织角色排序或人数上限无效")
        object.__setattr__(self, "permissions", permissions)


@dataclass(frozen=True)
class OrganizationTypeDefinition:
    id: StableId
    role_ids: frozenset[StableId]
    leader_role_id: StableId
    default_role_id: StableId
    capacity: int | None = None
    exclusive_membership: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="organization type id"))
        roles = frozenset(stable_id(value, field="organization role id") for value in self.role_ids)
        leader = stable_id(self.leader_role_id, field="organization role id")
        default = stable_id(self.default_role_id, field="organization role id")
        if not roles or leader not in roles or default not in roles:
            raise ValueError("组织类型角色集合无效")
        if self.capacity is not None and self.capacity < 1:
            raise ValueError("组织容量必须大于 0")
        object.__setattr__(self, "role_ids", roles)
        object.__setattr__(self, "leader_role_id", leader)
        object.__setattr__(self, "default_role_id", default)


@dataclass(frozen=True)
class SocialRequestDefinition:
    id: StableId
    maximum_lifetime_seconds: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="social request kind id"))
        if self.maximum_lifetime_seconds < 1:
            raise ValueError("社会请求最大期限必须大于 0")


@dataclass(frozen=True)
class RelationTypeDefinition:
    id: StableId
    minimum: int
    maximum: int
    initial: int = 0
    directed: bool = True
    overflow: RelationOverflowPolicy = RelationOverflowPolicy.REJECT

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", stable_id(self.id, field="relation type id"))
        if not self.minimum <= self.initial <= self.maximum:
            raise ValueError("社会关系数值范围无效")
        object.__setattr__(self, "overflow", RelationOverflowPolicy(self.overflow))


class SocialCatalog:
    def __init__(self) -> None:
        self.roles = DefinitionRegistry[OrganizationRoleDefinition]("OrganizationRole")
        self.organizations = DefinitionRegistry[OrganizationTypeDefinition]("OrganizationType")
        self.requests = DefinitionRegistry[SocialRequestDefinition]("SocialRequest")
        self.relations = DefinitionRegistry[RelationTypeDefinition]("RelationType")
        self._finalized = False

    def finalize(self) -> None:
        if self._finalized:
            return
        for organization in self.organizations:
            for role_id in organization.role_ids:
                self.roles.require(role_id)
            leader = self.roles.require(organization.leader_role_id)
            if DISSOLVE_PERMISSION not in leader.permissions:
                raise ValueError("组织领导角色必须拥有解散权限")
        for registry in (self.roles, self.organizations, self.requests, self.relations):
            registry.freeze()
        self._finalized = True

    @property
    def finalized(self) -> bool:
        return self._finalized


@dataclass(frozen=True)
class OrganizationMember:
    subject_id: str
    role_id: StableId
    joined_at: datetime
    contributions: Mapping[StableId, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.subject_id.strip():
            raise ValueError("组织成员缺少身份")
        object.__setattr__(self, "role_id", stable_id(self.role_id, field="organization role id"))
        _aware(self.joined_at, "OrganizationMember.joined_at")
        contributions = {
            stable_id(key, field="contribution kind id"): int(value)
            for key, value in self.contributions.items()
        }
        if any(value < 0 for value in contributions.values()):
            raise ValueError("组织贡献不能小于 0")
        object.__setattr__(self, "contributions", MappingProxyType(contributions))


@dataclass(frozen=True)
class Organization:
    id: str
    type_id: StableId
    founder_id: str
    members: Mapping[str, OrganizationMember]
    created_at: datetime
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.founder_id.strip() or self.revision < 0:
            raise ValueError("组织身份或 revision 无效")
        object.__setattr__(self, "type_id", stable_id(self.type_id, field="organization type id"))
        _aware(self.created_at, "Organization.created_at")
        members = dict(self.members)
        if any(key != value.subject_id for key, value in members.items()):
            raise ValueError("组织成员映射键与主体身份不一致")
        object.__setattr__(self, "members", MappingProxyType(members))
        object.__setattr__(self, "status", OrganizationStatus(self.status))


@dataclass(frozen=True)
class SocialRequest:
    id: str
    kind_id: StableId
    sender_id: str
    recipient_id: str
    created_at: datetime
    expires_at: datetime
    status: SocialRequestStatus = SocialRequestStatus.PENDING
    metadata: Mapping[str, object] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.sender_id.strip() or not self.recipient_id.strip():
            raise ValueError("社会请求缺少身份")
        if self.sender_id == self.recipient_id or self.revision < 0:
            raise ValueError("社会请求不能发给自己且 revision 不能小于 0")
        object.__setattr__(self, "kind_id", stable_id(self.kind_id, field="social request kind id"))
        _aware(self.created_at, "SocialRequest.created_at")
        _aware(self.expires_at, "SocialRequest.expires_at")
        if self.expires_at <= self.created_at:
            raise ValueError("社会请求期限必须晚于创建时间")
        object.__setattr__(self, "status", SocialRequestStatus(self.status))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class SocialRelation:
    type_id: StableId
    source_id: str
    target_id: str
    value: int
    updated_at: datetime
    revision: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "type_id", stable_id(self.type_id, field="relation type id"))
        if not self.source_id.strip() or not self.target_id.strip() or self.source_id == self.target_id:
            raise ValueError("社会关系主体无效")
        if self.revision < 0:
            raise ValueError("社会关系 revision 不能小于 0")
        _aware(self.updated_at, "SocialRelation.updated_at")

    @property
    def key(self) -> str:
        return f"{self.type_id}:{self.source_id}:{self.target_id}"


@dataclass(frozen=True)
class SocialState:
    scope_id: str
    organizations: Mapping[str, Organization] = field(default_factory=dict)
    requests: Mapping[str, SocialRequest] = field(default_factory=dict)
    relations: Mapping[str, SocialRelation] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.scope_id.strip() or self.revision < 0:
            raise ValueError("SocialState 身份或 revision 无效")
        organizations = dict(self.organizations)
        requests = dict(self.requests)
        relations = dict(self.relations)
        if any(key != value.id for key, value in organizations.items()):
            raise ValueError("组织映射键与 ID 不一致")
        if any(key != value.id for key, value in requests.items()):
            raise ValueError("社会请求映射键与 ID 不一致")
        if any(key != value.key for key, value in relations.items()):
            raise ValueError("社会关系映射键与内容不一致")
        object.__setattr__(self, "organizations", MappingProxyType(organizations))
        object.__setattr__(self, "requests", MappingProxyType(requests))
        object.__setattr__(self, "relations", MappingProxyType(relations))


@dataclass(frozen=True)
class CreateOrganization:
    organization_id: str
    type_id: StableId


@dataclass(frozen=True)
class JoinOrganization:
    organization_id: str
    subject_id: str


@dataclass(frozen=True)
class LeaveOrganization:
    organization_id: str
    subject_id: str


@dataclass(frozen=True)
class ChangeOrganizationRole:
    organization_id: str
    subject_id: str
    role_id: StableId


@dataclass(frozen=True)
class TransferOrganizationLeadership:
    organization_id: str
    current_leader_id: str
    next_leader_id: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.organization_id.strip(),
                self.current_leader_id.strip(),
                self.next_leader_id.strip(),
            )
        ):
            raise ValueError("领导权转移缺少身份")
        if self.current_leader_id == self.next_leader_id:
            raise ValueError("领导权不能转移给当前领导者")


@dataclass(frozen=True)
class AddOrganizationContribution:
    organization_id: str
    subject_id: str
    kind_id: StableId
    amount: int


@dataclass(frozen=True)
class DissolveOrganization:
    organization_id: str


@dataclass(frozen=True)
class CreateSocialRequest:
    request: SocialRequest


@dataclass(frozen=True)
class ResolveSocialRequest:
    request_id: str
    status: SocialRequestStatus


@dataclass(frozen=True)
class AdjustSocialRelation:
    type_id: StableId
    source_id: str
    target_id: str
    amount: int


@dataclass(frozen=True)
class SocialCommand:
    id: str
    actor_id: str
    expected_revision: int
    operation: object

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.actor_id.strip() or self.expected_revision < 0:
            raise ValueError("SocialCommand 身份或 revision 无效")


@dataclass(frozen=True)
class SocialExecution:
    command_id: str
    state: SocialState
    events: tuple[RuleEvent, ...]


def relation_key(definition: RelationTypeDefinition, source_id: str, target_id: str) -> str:
    if not definition.directed and source_id > target_id:
        source_id, target_id = target_id, source_id
    return f"{definition.id}:{source_id}:{target_id}"


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} 必须包含时区")


__all__ = [
    "DISSOLVE_PERMISSION",
    "MANAGE_MEMBERS_PERMISSION",
    "MANAGE_ROLES_PERMISSION",
    "AddOrganizationContribution",
    "AdjustSocialRelation",
    "ChangeOrganizationRole",
    "CreateOrganization",
    "CreateSocialRequest",
    "DissolveOrganization",
    "JoinOrganization",
    "LeaveOrganization",
    "Organization",
    "OrganizationMember",
    "OrganizationRoleDefinition",
    "OrganizationStatus",
    "OrganizationTypeDefinition",
    "RelationOverflowPolicy",
    "RelationTypeDefinition",
    "ResolveSocialRequest",
    "SocialCatalog",
    "SocialCommand",
    "SocialExecution",
    "SocialRelation",
    "SocialRequest",
    "SocialRequestDefinition",
    "SocialRequestStatus",
    "SocialState",
    "TransferOrganizationLeadership",
    "relation_key",
]
