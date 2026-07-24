"""Remaining domain repositories."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refresh_token import RefreshToken
from app.db.models.role import Permission, Role
from app.db.models.scan import Scan
from app.db.models.target import Target
from app.db.models.report import Report
from app.db.models.audit_log import AuditLog
from app.core.constants import AuditEventType, AuditStatus, ScanStatus
from app.repositories.base_repository import BaseRepository


# ---------------------------------------------------------------------------
# Role Repository
# ---------------------------------------------------------------------------

class RoleRepository(BaseRepository[Role]):
    model = Role

    async def get_by_name(self, name: str) -> Role | None:
        result = await self.session.execute(
            select(Role).where(Role.name == name, Role.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_many_by_names(self, names: list[str]) -> Sequence[Role]:
        result = await self.session.execute(
            select(Role).where(Role.name.in_(names), Role.deleted_at.is_(None))
        )
        return result.scalars().all()


# ---------------------------------------------------------------------------
# RefreshToken Repository
# ---------------------------------------------------------------------------

class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Look up a refresh token by its SHA-256 hash."""
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_active_by_user(self, user_id: uuid.UUID) -> Sequence[RefreshToken]:
        """Return all non-revoked, non-expired tokens for a user."""
        now = datetime.now(tz=timezone.utc)
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        return result.scalars().all()

    async def revoke_token(self, token: RefreshToken) -> RefreshToken:
        return await self.update(token, revoked_at=datetime.now(tz=timezone.utc))

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        """Revoke all tokens in a rotation family (replay attack response)."""
        tokens_result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        now = datetime.now(tz=timezone.utc)
        for token in tokens_result.scalars().all():
            token.revoked_at = now
            self.session.add(token)
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Revoke every active refresh token for a user (logout everywhere)."""
        tokens = await self.get_active_by_user(user_id)
        now = datetime.now(tz=timezone.utc)
        for token in tokens:
            token.revoked_at = now
            self.session.add(token)
        await self.session.flush()


# ---------------------------------------------------------------------------
# Target Repository
# ---------------------------------------------------------------------------

class TargetRepository(BaseRepository[Target]):
    model = Target

    async def get_by_owner(
        self, owner_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[Sequence[Target], int]:
        filters = [Target.owner_id == owner_id]
        targets = await self.get_all(skip=skip, limit=limit, filters=filters)
        total = await self.count(filters=filters)
        return targets, total

    async def get_by_id_and_owner(
        self, target_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Target | None:
        result = await self.session.execute(
            select(Target).where(
                Target.id == target_id,
                Target.owner_id == owner_id,
                Target.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Scan Repository
# ---------------------------------------------------------------------------

class ScanRepository(BaseRepository[Scan]):
    model = Scan

    async def get_by_target(
        self, target_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[Sequence[Scan], int]:
        filters = [Scan.target_id == target_id]
        scans = await self.get_all(skip=skip, limit=limit, filters=filters)
        total = await self.count(filters=filters)
        return scans, total

    async def get_by_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[Sequence[Scan], int]:
        filters = [Scan.created_by == user_id]
        scans = await self.get_all(skip=skip, limit=limit, filters=filters)
        total = await self.count(filters=filters)
        return scans, total

    async def update_status(
        self,
        scan: Scan,
        status: ScanStatus,
        celery_task_id: str | None = None,
    ) -> Scan:
        kwargs: dict = {"status": status}
        if celery_task_id is not None:
            kwargs["celery_task_id"] = celery_task_id
        if status == ScanStatus.RUNNING:
            kwargs["started_at"] = datetime.now(tz=timezone.utc)
        if status in (ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED):
            kwargs["completed_at"] = datetime.now(tz=timezone.utc)
        return await self.update(scan, **kwargs)


# ---------------------------------------------------------------------------
# Report Repository
# ---------------------------------------------------------------------------

class ReportRepository(BaseRepository[Report]):
    model = Report

    async def get_by_scan(self, scan_id: uuid.UUID) -> Sequence[Report]:
        result = await self.session.execute(
            select(Report).where(
                Report.scan_id == scan_id, Report.deleted_at.is_(None)
            )
        )
        return result.scalars().all()


# ---------------------------------------------------------------------------
# AuditLog Repository
# ---------------------------------------------------------------------------

class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def log(
        self,
        event_type: AuditEventType,
        status: AuditStatus = AuditStatus.SUCCESS,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> AuditLog:
        """Create an immutable audit log entry."""
        return await self.create(
            event_type=event_type,
            status=status,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip_address,
            user_agent=user_agent,
            old_value=old_value,
            new_value=new_value,
        )

    async def get_by_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> Sequence[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
