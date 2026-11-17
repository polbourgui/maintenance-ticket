from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from app.core.config import Settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.domain.rbac import AccessPolicy, Permission
from app.models import Role, Site, User
from app.repositories import UnitOfWork
from app.schemas.tickets import TicketEventRead, TicketRead
from app.schemas.users import PersonalDataExport, UserCreate, UserRead, UserUpdate
from app.services.auth import validate_password_strength

ANONYMIZED_NAME = "Utilisateur supprimé"


class UserService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self.uow = uow
        self.settings = settings

    def create(self, policy: AccessPolicy, data: UserCreate) -> User:
        policy.require(Permission.USER_MANAGE)
        if self.uow.users.get_by_email(data.email) is not None:
            raise ConflictError("A user with this e-mail already exists")
        validate_password_strength(data.password, self.settings, email=data.email)
        user = User(
            email=data.email.lower(),
            full_name=data.full_name,
            phone=data.phone,
            role=data.role,
            hashed_password=hash_password(data.password),
            is_active=True,
            token_version=0,
        )
        user.sites = self._resolve_sites(data.site_ids)
        self.uow.users.add(user)
        self.uow.commit()
        return user

    def search(
        self,
        policy: AccessPolicy,
        *,
        offset: int,
        limit: int,
        role: Role | None,
        site_id: uuid.UUID | None,
    ) -> tuple[list[User], int]:
        policy.require(Permission.USER_MANAGE)
        return self.uow.users.search(offset=offset, limit=limit, role=role, site_id=site_id)

    def get(self, policy: AccessPolicy, user_id: uuid.UUID) -> User:
        policy.require(Permission.USER_MANAGE)
        return self._get(user_id)

    def update(self, policy: AccessPolicy, user_id: uuid.UUID, data: UserUpdate) -> User:
        policy.require(Permission.USER_MANAGE)
        user = self._get(user_id)
        if user.anonymized_at is not None:
            raise BusinessRuleError("Anonymized accounts cannot be modified")
        changes = data.model_dump(exclude_unset=True)
        if user.id == policy.user.id and (
            changes.get("is_active") is False or changes.get("role", Role.ADMIN) != Role.ADMIN
        ):
            raise BusinessRuleError("Administrators cannot demote or deactivate themselves")
        if "site_ids" in changes:
            user.sites = self._resolve_sites(changes.pop("site_ids") or [])
        security_relevant = "role" in changes or changes.get("is_active") is False
        for field, value in changes.items():
            setattr(user, field, value)
        if security_relevant:
            self._revoke_sessions(user)
        self.uow.commit()
        return user

    # -- GDPR -----------------------------------------------------------------------------
    def export_personal_data(self, user: User) -> PersonalDataExport:
        now = datetime.now(UTC)
        return PersonalDataExport(
            generated_at=now,
            profile=UserRead.model_validate(user),
            tickets_created=[
                TicketRead.from_entity(t).model_dump(mode="json")
                for t in self.uow.tickets.list_created_by(user.id)
            ],
            ticket_events=[
                TicketEventRead.model_validate(e).model_dump(mode="json")
                for e in self.uow.ticket_events.list_by_actor(user.id)
            ],
            active_sessions=self.uow.refresh_tokens.count_active_for_user(user.id, now),
        )

    def anonymize(self, policy: AccessPolicy, user_id: uuid.UUID) -> User:
        """Right to erasure (GDPR art. 17).

        Maintenance records of ERP sites must be retained (legal obligation: registre de
        sécurité), so the account is *anonymized* rather than deleted: identifying data is
        irreversibly replaced, sessions are revoked, the audit trail keeps an opaque id.
        """
        if policy.user.id != user_id:
            policy.require(Permission.USER_MANAGE)
        user = self._get(user_id)
        if user.anonymized_at is not None:
            return user
        if user.role is Role.ADMIN and self._is_last_active_admin(user):
            raise BusinessRuleError("The last active administrator cannot be anonymized")
        user.email = f"deleted-{uuid.uuid4().hex}@anonymized.invalid"
        user.full_name = ANONYMIZED_NAME
        user.phone = None
        user.hashed_password = hash_password(secrets.token_urlsafe(32))
        user.is_active = False
        user.sites = []
        user.last_login_at = None
        user.anonymized_at = datetime.now(UTC)
        self._revoke_sessions(user)
        self.uow.commit()
        return user

    # -- helpers --------------------------------------------------------------------------
    def _get(self, user_id: uuid.UUID) -> User:
        user = self.uow.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def _resolve_sites(self, site_ids: list[uuid.UUID]) -> list[Site]:
        unique: set[uuid.UUID] = set(site_ids)
        sites = self.uow.sites.get_many(unique)
        if len(sites) != len(unique):
            raise NotFoundError("One or more sites do not exist")
        return sites

    def _revoke_sessions(self, user: User) -> None:
        user.token_version += 1
        self.uow.refresh_tokens.revoke_all_for_user(user.id, datetime.now(UTC))

    def _is_last_active_admin(self, user: User) -> bool:
        admins, _ = self.uow.users.search(offset=0, limit=2, role=Role.ADMIN)
        return [a.id for a in admins if a.is_active] == [user.id]
