"""
User, Target, Scan, and Report services — business logic layer.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditEventType, ScanStatus
from app.core.exceptions import NotFoundError, OwnershipError, ConflictError
from app.core.logging import get_logger
from app.core.security import hash_password, validate_password_strength
from app.repositories import (
    AuditLogRepository,
    ReportRepository,
    ScanRepository,
    TargetRepository,
    UserRepository,
)
from app.schemas.report import ReportCreate
from app.schemas.scan import ScanCreate
from app.schemas.target import TargetCreate, TargetUpdate
from app.schemas.user import UserUpdate
from app.worker.tasks import execute_scan

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# User Service
# ---------------------------------------------------------------------------

class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)
        self._audit = AuditLogRepository(session)

    async def get_user(self, user_id: uuid.UUID) -> "User":
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def list_users(
        self, skip: int = 0, limit: int = 20, is_active: bool | None = None
    ) -> tuple[Sequence["User"], int]:
        return await self._users.list_users(skip=skip, limit=limit, is_active=is_active)

    async def update_user(
        self,
        user_id: uuid.UUID,
        payload: UserUpdate,
        requesting_user_id: uuid.UUID,
        is_admin: bool = False,
    ) -> "User":
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if not is_admin and user_id != requesting_user_id:
            raise OwnershipError()

        updates: dict = {}
        if payload.email and payload.email != user.email:
            if await self._users.email_exists(payload.email):
                raise ConflictError("Email is already in use.")
            updates["email"] = payload.email.lower().strip()
        if payload.username and payload.username != user.username:
            if await self._users.username_exists(payload.username):
                raise ConflictError("Username is already taken.")
            updates["username"] = payload.username.strip()
        if payload.password:
            validate_password_strength(payload.password)
            updates["hashed_password"] = hash_password(payload.password)
        if payload.is_active is not None and is_admin:
            updates["is_active"] = payload.is_active

        if updates:
            user = await self._users.update(user, **updates)
            await self._audit.log(
                event_type=AuditEventType.USER_UPDATED,
                user_id=requesting_user_id,
                resource_type="user",
                resource_id=str(user_id),
            )
        return user

    async def deactivate_user(self, user_id: uuid.UUID, admin_id: uuid.UUID) -> "User":
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        user = await self._users.update(user, is_active=False)
        await self._audit.log(
            event_type=AuditEventType.USER_DELETED,
            user_id=admin_id,
            resource_type="user",
            resource_id=str(user_id),
        )
        return user


# ---------------------------------------------------------------------------
# Target Service
# ---------------------------------------------------------------------------

class TargetService:
    def __init__(self, session: AsyncSession) -> None:
        self._targets = TargetRepository(session)

    async def create_target(self, payload: TargetCreate, owner_id: uuid.UUID) -> "Target":
        return await self._targets.create(
            id=uuid.uuid4(),
            owner_id=owner_id,
            name=payload.name,
            host=payload.host,
            description=payload.description,
            port_range=payload.port_range,
            tags=payload.tags,
        )

    async def get_target(self, target_id: uuid.UUID, owner_id: uuid.UUID, is_admin: bool = False) -> "Target":
        if is_admin:
            target = await self._targets.get_by_id(target_id)
        else:
            target = await self._targets.get_by_id_and_owner(target_id, owner_id)
        if target is None:
            raise NotFoundError("Target not found.")
        return target

    async def list_targets(
        self, owner_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[Sequence["Target"], int]:
        return await self._targets.get_by_owner(owner_id, skip=skip, limit=limit)

    async def update_target(
        self, target_id: uuid.UUID, payload: TargetUpdate, owner_id: uuid.UUID
    ) -> "Target":
        target = await self._targets.get_by_id_and_owner(target_id, owner_id)
        if target is None:
            raise NotFoundError("Target not found.")
        updates = payload.model_dump(exclude_none=True)
        return await self._targets.update(target, **updates)

    async def delete_target(self, target_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        target = await self._targets.get_by_id_and_owner(target_id, owner_id)
        if target is None:
            raise NotFoundError("Target not found.")
        await self._targets.soft_delete(target)


# ---------------------------------------------------------------------------
# Scan Service
# ---------------------------------------------------------------------------

class ScanService:
    def __init__(self, session: AsyncSession) -> None:
        self._scans = ScanRepository(session)
        self._targets = TargetRepository(session)
        self._audit = AuditLogRepository(session)

    async def create_scan(self, payload: ScanCreate, created_by: uuid.UUID) -> "Scan":
        target = await self._targets.get_by_id(payload.target_id)
        if target is None:
            raise NotFoundError("Target not found.")

        scan = await self._scans.create(
            id=uuid.uuid4(),
            target_id=payload.target_id,
            created_by=created_by,
            scan_type=payload.scan_type,
            scan_options=payload.scan_options,
            status=ScanStatus.QUEUED,
        )

        # Dispatch background task
        task = execute_scan.delay(str(scan.id))
        scan = await self._scans.update_status(scan, ScanStatus.QUEUED, celery_task_id=task.id)

        await self._audit.log(
            event_type=AuditEventType.SCAN_CREATED,
            user_id=created_by,
            resource_type="scan",
            resource_id=str(scan.id),
        )
        return scan

    async def get_scan(self, scan_id: uuid.UUID, user_id: uuid.UUID, is_admin: bool = False) -> "Scan":
        scan = await self._scans.get_by_id(scan_id)
        if scan is None:
            raise NotFoundError("Scan not found.")
        if not is_admin and scan.created_by != user_id:
            raise OwnershipError()
        return scan

    async def list_user_scans(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[Sequence["Scan"], int]:
        return await self._scans.get_by_user(user_id, skip=skip, limit=limit)

    async def cancel_scan(self, scan_id: uuid.UUID, user_id: uuid.UUID) -> "Scan":
        scan = await self._scans.get_by_id(scan_id)
        if scan is None:
            raise NotFoundError("Scan not found.")
        if scan.created_by != user_id:
            raise OwnershipError()
        if scan.status not in (ScanStatus.PENDING, ScanStatus.QUEUED):
            raise ConflictError(f"Cannot cancel a scan with status '{scan.status}'.")

        scan = await self._scans.update_status(scan, ScanStatus.CANCELLED)
        
        # Try to revoke the background task if it's still queued
        if scan.celery_task_id:
            from app.core.celery_app import celery_app
            celery_app.control.revoke(scan.celery_task_id, terminate=True)

        await self._audit.log(
            event_type=AuditEventType.SCAN_CANCELLED,
            user_id=user_id,
            resource_type="scan",
            resource_id=str(scan_id),
        )
        return scan


# ---------------------------------------------------------------------------
# Report Service
# ---------------------------------------------------------------------------

class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self._reports = ReportRepository(session)
        self._scans = ScanRepository(session)
        self._audit = AuditLogRepository(session)

    async def create_report(self, payload: ReportCreate, generated_by: uuid.UUID) -> "Report":
        scan = await self._scans.get_by_id(payload.scan_id)
        if scan is None:
            raise NotFoundError("Scan not found.")
        if scan.status != ScanStatus.COMPLETED:
            raise ConflictError("Reports can only be generated for completed scans.")

        report = await self._reports.create(
            id=uuid.uuid4(),
            scan_id=payload.scan_id,
            generated_by=generated_by,
            title=payload.title,
            summary=payload.summary,
            format=payload.format,
            is_public=payload.is_public,
        )

        await self._audit.log(
            event_type=AuditEventType.REPORT_GENERATED,
            user_id=generated_by,
            resource_type="report",
            resource_id=str(report.id),
        )
        return report

    async def get_report(self, report_id: uuid.UUID) -> "Report":
        report = await self._reports.get_by_id(report_id)
        if report is None:
            raise NotFoundError("Report not found.")
        return report

    async def list_scan_reports(self, scan_id: uuid.UUID) -> Sequence["Report"]:
        return await self._reports.get_by_scan(scan_id)


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.target import Target
    from app.db.models.scan import Scan
    from app.db.models.report import Report
