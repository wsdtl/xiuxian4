"""组织、社会请求和主体关系的纯规则状态机。"""

from __future__ import annotations

from dataclasses import replace

from ..context import RuleContext
from ..errors import RuleOutcome, RuleViolation
from ..events import RuleEvent
from .models import (
    DISSOLVE_PERMISSION,
    MANAGE_MEMBERS_PERMISSION,
    MANAGE_ROLES_PERMISSION,
    AddOrganizationContribution,
    AdjustSocialRelation,
    ChangeOrganizationRole,
    CreateOrganization,
    CreateSocialRequest,
    DissolveOrganization,
    JoinOrganization,
    LeaveOrganization,
    Organization,
    OrganizationMember,
    OrganizationStatus,
    RelationOverflowPolicy,
    ResolveSocialRequest,
    SocialCatalog,
    SocialCommand,
    SocialExecution,
    SocialRelation,
    SocialRequestStatus,
    SocialState,
    TransferOrganizationLeadership,
    relation_key,
)


class SocialEngine:
    def __init__(self, catalog: SocialCatalog) -> None:
        if not catalog.finalized:
            catalog.finalize()
        self.catalog = catalog

    def execute(
        self,
        command: SocialCommand,
        *,
        state: SocialState,
        context: RuleContext,
    ) -> RuleOutcome[SocialExecution]:
        checkpoint = context.random.checkpoint()
        try:
            if state.revision != command.expected_revision:
                self._fail(
                    "social.revision_conflict",
                    "社会状态版本与命令预期不一致",
                    {"expected": command.expected_revision, "actual": state.revision},
                )
            organizations = dict(state.organizations)
            requests = dict(state.requests)
            relations = dict(state.relations)
            operation = command.operation
            if isinstance(operation, CreateOrganization):
                kind, target, subject, values = self._create_organization(
                    command, operation, organizations, context
                )
            elif isinstance(operation, JoinOrganization):
                kind, target, subject, values = self._join(
                    command, operation, organizations, context
                )
            elif isinstance(operation, LeaveOrganization):
                kind, target, subject, values = self._leave(command, operation, organizations)
            elif isinstance(operation, ChangeOrganizationRole):
                kind, target, subject, values = self._change_role(
                    command, operation, organizations
                )
            elif isinstance(operation, TransferOrganizationLeadership):
                kind, target, subject, values = self._transfer_leadership(
                    command, operation, organizations
                )
            elif isinstance(operation, AddOrganizationContribution):
                kind, target, subject, values = self._contribute(operation, organizations)
            elif isinstance(operation, DissolveOrganization):
                kind, target, subject, values = self._dissolve(
                    command, operation, organizations
                )
            elif isinstance(operation, CreateSocialRequest):
                kind, target, subject, values = self._create_request(
                    command, operation, requests, context
                )
            elif isinstance(operation, ResolveSocialRequest):
                kind, target, subject, values = self._resolve_request(
                    command, operation, requests, context
                )
            elif isinstance(operation, AdjustSocialRelation):
                kind, target, subject, values = self._adjust_relation(
                    operation, relations, context
                )
            else:
                raise TypeError(f"未知社会操作：{type(operation).__name__}")
            next_state = SocialState(
                state.scope_id,
                organizations,
                requests,
                relations,
                state.revision + 1,
            )
            event = RuleEvent.from_context(
                context,
                kind=kind,
                source_id=command.actor_id,
                target_id=target,
                subject_id=subject,
                values={"command_id": command.id, **values},
            )
            return RuleOutcome.success(SocialExecution(command.id, next_state, (event,)))
        except RuleViolation as exc:
            context.random.restore(checkpoint)
            return RuleOutcome.failed(exc.failure)

    def _create_organization(self, command, operation, organizations, context):
        if operation.organization_id in organizations:
            self._fail("organization.exists", "组织已经存在")
        definition = self.catalog.organizations.require(operation.type_id)
        if definition.exclusive_membership and self._membership(
            organizations, definition.id, command.actor_id
        ):
            self._fail("organization.exclusive_membership", "当前主体已加入同类型组织")
        founder = OrganizationMember(
            command.actor_id,
            definition.leader_role_id,
            context.logical_time,
        )
        organization = Organization(
            operation.organization_id,
            definition.id,
            command.actor_id,
            {command.actor_id: founder},
            context.logical_time,
        )
        organizations[organization.id] = organization
        return "organization.created", organization.id, definition.id, {
            "founder_id": command.actor_id
        }

    def _join(self, command, operation, organizations, context):
        organization = self._organization(organizations, operation.organization_id)
        definition = self.catalog.organizations.require(organization.type_id)
        if organization.status is not OrganizationStatus.ACTIVE:
            self._fail("organization.inactive", "组织已经解散")
        if command.actor_id != operation.subject_id:
            self._require_permission(organization, command.actor_id, MANAGE_MEMBERS_PERMISSION)
        if operation.subject_id in organization.members:
            self._fail("organization.already_member", "主体已经是组织成员")
        if definition.capacity is not None and len(organization.members) >= definition.capacity:
            self._fail("organization.capacity_reached", "组织容量已经用尽")
        if definition.exclusive_membership and self._membership(
            organizations, definition.id, operation.subject_id
        ):
            self._fail("organization.exclusive_membership", "主体已加入同类型组织")
        members = dict(organization.members)
        members[operation.subject_id] = OrganizationMember(
            operation.subject_id,
            definition.default_role_id,
            context.logical_time,
        )
        organizations[organization.id] = replace(
            organization,
            members=members,
            revision=organization.revision + 1,
        )
        return "organization.member.joined", organization.id, organization.type_id, {
            "subject_id": operation.subject_id,
            "role_id": definition.default_role_id,
        }

    def _leave(self, command, operation, organizations):
        organization = self._organization(organizations, operation.organization_id)
        member = organization.members.get(operation.subject_id)
        if member is None:
            self._fail("organization.not_member", "主体不是组织成员")
        if command.actor_id != operation.subject_id:
            self._require_permission(organization, command.actor_id, MANAGE_MEMBERS_PERMISSION)
        definition = self.catalog.organizations.require(organization.type_id)
        if member.role_id == definition.leader_role_id:
            self._fail("organization.leader_cannot_leave", "领导者必须先转移角色或解散组织")
        members = dict(organization.members)
        del members[operation.subject_id]
        organizations[organization.id] = replace(
            organization,
            members=members,
            revision=organization.revision + 1,
        )
        return "organization.member.left", organization.id, organization.type_id, {
            "subject_id": operation.subject_id
        }

    def _change_role(self, command, operation, organizations):
        organization = self._organization(organizations, operation.organization_id)
        self._require_permission(organization, command.actor_id, MANAGE_ROLES_PERMISSION)
        definition = self.catalog.organizations.require(organization.type_id)
        if operation.role_id not in definition.role_ids:
            self._fail("organization.role_rejected", "角色不属于该组织类型")
        member = organization.members.get(operation.subject_id)
        if member is None:
            self._fail("organization.not_member", "主体不是组织成员")
        role = self.catalog.roles.require(operation.role_id)
        if role.maximum_members is not None:
            count = sum(value.role_id == role.id for value in organization.members.values())
            if member.role_id != role.id and count >= role.maximum_members:
                self._fail("organization.role_capacity", "组织角色人数已经达到上限")
        if member.role_id == definition.leader_role_id and operation.role_id != member.role_id:
            other_leaders = sum(
                value.role_id == definition.leader_role_id
                for key, value in organization.members.items()
                if key != member.subject_id
            )
            if not other_leaders:
                self._fail("organization.last_leader", "组织必须保留至少一名领导者")
        members = dict(organization.members)
        members[member.subject_id] = replace(member, role_id=operation.role_id)
        organizations[organization.id] = replace(
            organization,
            members=members,
            revision=organization.revision + 1,
        )
        return "organization.member.role_changed", organization.id, organization.type_id, {
            "subject_id": member.subject_id,
            "previous_role_id": member.role_id,
            "current_role_id": operation.role_id,
        }

    def _transfer_leadership(self, command, operation, organizations):
        organization = self._organization(organizations, operation.organization_id)
        if organization.status is not OrganizationStatus.ACTIVE:
            self._fail("organization.inactive", "组织已经解散")
        definition = self.catalog.organizations.require(organization.type_id)
        current = organization.members.get(operation.current_leader_id)
        successor = organization.members.get(operation.next_leader_id)
        if current is None or successor is None:
            self._fail("organization.not_member", "领导权转移双方都必须是组织成员")
        if command.actor_id != current.subject_id:
            self._fail("organization.leader_required", "只有当前领导者可以转移领导权")
        if current.role_id != definition.leader_role_id:
            self._fail("organization.current_leader_mismatch", "指定主体不是当前领导者")
        if successor.role_id == definition.leader_role_id:
            self._fail("organization.successor_already_leader", "接任者已经是领导者")
        default_role = self.catalog.roles.require(definition.default_role_id)
        if default_role.maximum_members is not None:
            default_count = sum(
                member.role_id == default_role.id
                for member in organization.members.values()
            )
            if successor.role_id == default_role.id:
                default_count -= 1
            if default_count + 1 > default_role.maximum_members:
                self._fail("organization.role_capacity", "卸任后的默认角色人数已经达到上限")
        members = dict(organization.members)
        members[current.subject_id] = replace(current, role_id=definition.default_role_id)
        members[successor.subject_id] = replace(
            successor,
            role_id=definition.leader_role_id,
        )
        organizations[organization.id] = replace(
            organization,
            members=members,
            revision=organization.revision + 1,
        )
        return "organization.leadership.transferred", organization.id, organization.type_id, {
            "previous_leader_id": current.subject_id,
            "current_leader_id": successor.subject_id,
        }

    def _contribute(self, operation, organizations):
        organization = self._organization(organizations, operation.organization_id)
        member = organization.members.get(operation.subject_id)
        if member is None:
            self._fail("organization.not_member", "主体不是组织成员")
        if operation.amount <= 0:
            self._fail("organization.invalid_contribution", "组织贡献必须大于 0")
        kind_id = str(operation.kind_id)
        contributions = dict(member.contributions)
        contributions[kind_id] = contributions.get(kind_id, 0) + operation.amount
        members = dict(organization.members)
        members[member.subject_id] = replace(member, contributions=contributions)
        organizations[organization.id] = replace(
            organization,
            members=members,
            revision=organization.revision + 1,
        )
        return "organization.contribution.added", organization.id, organization.type_id, {
            "subject_id": member.subject_id,
            "kind_id": kind_id,
            "amount": operation.amount,
            "total": contributions[kind_id],
        }

    def _dissolve(self, command, operation, organizations):
        organization = self._organization(organizations, operation.organization_id)
        self._require_permission(organization, command.actor_id, DISSOLVE_PERMISSION)
        if organization.status is not OrganizationStatus.ACTIVE:
            self._fail("organization.inactive", "组织已经解散")
        organizations[organization.id] = replace(
            organization,
            status=OrganizationStatus.DISSOLVED,
            revision=organization.revision + 1,
        )
        return "organization.dissolved", organization.id, organization.type_id, {}

    def _create_request(self, command, operation, requests, context):
        request = operation.request
        if request.id in requests:
            self._fail("social.request_exists", "社会请求已经存在")
        definition = self.catalog.requests.require(request.kind_id)
        if request.sender_id != command.actor_id or request.status is not SocialRequestStatus.PENDING:
            self._fail("social.request_sender_mismatch", "请求发送者与行为人不一致")
        if request.created_at != context.logical_time:
            self._fail("social.request_time_mismatch", "请求创建时间必须等于逻辑时间")
        lifetime = int((request.expires_at - request.created_at).total_seconds())
        if lifetime > definition.maximum_lifetime_seconds:
            self._fail("social.request_lifetime", "社会请求期限超过定义上限")
        requests[request.id] = request
        return "social.request.created", request.recipient_id, request.kind_id, {
            "request_id": request.id,
            "sender_id": request.sender_id,
        }

    def _resolve_request(self, command, operation, requests, context):
        request = requests.get(operation.request_id)
        if request is None:
            self._fail("social.request_unknown", "找不到社会请求")
        if request.status is not SocialRequestStatus.PENDING:
            self._fail("social.request_terminal", "社会请求已经终结")
        status = SocialRequestStatus(operation.status)
        if status in {SocialRequestStatus.ACCEPTED, SocialRequestStatus.REJECTED}:
            if command.actor_id != request.recipient_id:
                self._fail("social.request_recipient_required", "只有接收方可以处理请求")
            if context.logical_time >= request.expires_at:
                self._fail("social.request_expired", "社会请求已经过期")
        elif status is SocialRequestStatus.CANCELLED:
            if command.actor_id != request.sender_id:
                self._fail("social.request_sender_required", "只有发送方可以取消请求")
        elif status is SocialRequestStatus.EXPIRED:
            if context.logical_time < request.expires_at:
                self._fail("social.request_not_expired", "社会请求尚未过期")
        else:
            self._fail("social.request_status", "请求只能进入明确终态")
        request = replace(request, status=status, revision=request.revision + 1)
        requests[request.id] = request
        return f"social.request.{status.value}", request.recipient_id, request.kind_id, {
            "request_id": request.id,
            "sender_id": request.sender_id,
        }

    def _adjust_relation(self, operation, relations, context):
        definition = self.catalog.relations.require(operation.type_id)
        key = relation_key(definition, operation.source_id, operation.target_id)
        source_id, target_id = operation.source_id, operation.target_id
        if not definition.directed and source_id > target_id:
            source_id, target_id = target_id, source_id
        previous = relations.get(key)
        previous_value = previous.value if previous else definition.initial
        requested = previous_value + operation.amount
        if definition.overflow is RelationOverflowPolicy.CLAMP:
            current = max(definition.minimum, min(definition.maximum, requested))
        elif not definition.minimum <= requested <= definition.maximum:
            self._fail("social.relation_out_of_range", "社会关系变化超出范围")
        else:
            current = requested
        relation = SocialRelation(
            definition.id,
            source_id,
            target_id,
            current,
            context.logical_time,
            (previous.revision + 1) if previous else 0,
        )
        relations[key] = relation
        return "social.relation.adjusted", target_id, definition.id, {
            "source_id": source_id,
            "previous": previous_value,
            "current": current,
            "requested": requested,
        }

    def _require_permission(self, organization, subject_id, permission_id):
        member = organization.members.get(subject_id)
        if member is None:
            self._fail("organization.permission_denied", "行为人不是组织成员")
        role = self.catalog.roles.require(member.role_id)
        if permission_id not in role.permissions:
            self._fail("organization.permission_denied", "组织角色缺少所需权限")

    def _membership(self, organizations, type_id, subject_id):
        return any(
            organization.type_id == type_id
            and organization.status is OrganizationStatus.ACTIVE
            and subject_id in organization.members
            for organization in organizations.values()
        )

    @staticmethod
    def _organization(organizations, organization_id):
        organization = organizations.get(organization_id)
        if organization is None:
            SocialEngine._fail("organization.unknown", "找不到组织")
        return organization

    @staticmethod
    def _fail(code: str, message: str, details: dict[str, object] | None = None) -> None:
        raise RuleViolation(code, message, details or {})


__all__ = ["SocialEngine"]
