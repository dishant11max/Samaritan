"""Target, Scan, and Report endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.dependencies import ActiveUserDep, DBDep
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.report import ReportCreate, ReportResponse
from app.schemas.scan import ScanCreate, ScanResponse
from app.schemas.target import TargetCreate, TargetResponse, TargetUpdate
from app.services.services import ReportService, ScanService, TargetService
from app.utils import paginate, success_response
from app.core.rate_limit import limiter

# ---------------------------------------------------------------------------
# Targets Router
# ---------------------------------------------------------------------------

targets_router = APIRouter(prefix="/targets", tags=["Targets"])


@targets_router.post("", response_model=APIResponse[TargetResponse], status_code=201)
@limiter.limit("20/minute")
async def create_target(payload: TargetCreate, request: Request, db: DBDep, current_user: ActiveUserDep):
    svc = TargetService(db)
    target = await svc.create_target(payload, owner_id=current_user.id)
    return success_response(data=TargetResponse.model_validate(target), message="Target created.")


@targets_router.get("", response_model=PaginatedResponse[TargetResponse])
@limiter.limit("60/minute")
async def list_targets(
    request: Request,
    db: DBDep,
    current_user: ActiveUserDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = TargetService(db)
    targets, total = await svc.list_targets(
        owner_id=current_user.id,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return paginate(
        items=[TargetResponse.model_validate(t) for t in targets],
        total=total,
        page=page,
        page_size=page_size,
    )


@targets_router.get("/{target_id}", response_model=APIResponse[TargetResponse])
@limiter.limit("60/minute")
async def get_target(target_id: uuid.UUID, request: Request, db: DBDep, current_user: ActiveUserDep):
    svc = TargetService(db)
    target = await svc.get_target(target_id, owner_id=current_user.id)
    return success_response(data=TargetResponse.model_validate(target))


@targets_router.put("/{target_id}", response_model=APIResponse[TargetResponse])
@limiter.limit("30/minute")
async def update_target(
    target_id: uuid.UUID, payload: TargetUpdate, request: Request, db: DBDep, current_user: ActiveUserDep
):
    svc = TargetService(db)
    target = await svc.update_target(target_id, payload, owner_id=current_user.id)
    return success_response(data=TargetResponse.model_validate(target), message="Target updated.")


@targets_router.delete("/{target_id}", response_model=APIResponse[None])
@limiter.limit("10/minute")
async def delete_target(target_id: uuid.UUID, request: Request, db: DBDep, current_user: ActiveUserDep):
    svc = TargetService(db)
    await svc.delete_target(target_id, owner_id=current_user.id)
    return success_response(message="Target deleted.")


# ---------------------------------------------------------------------------
# Scans Router
# ---------------------------------------------------------------------------

scans_router = APIRouter(prefix="/scans", tags=["Scans"])


@scans_router.post("", response_model=APIResponse[ScanResponse], status_code=201)
@limiter.limit("10/minute")
async def create_scan(payload: ScanCreate, request: Request, db: DBDep, current_user: ActiveUserDep):
    svc = ScanService(db)
    scan = await svc.create_scan(payload, created_by=current_user.id)
    return success_response(data=ScanResponse.model_validate(scan), message="Scan queued.")


@scans_router.get("", response_model=PaginatedResponse[ScanResponse])
@limiter.limit("60/minute")
async def list_scans(
    request: Request,
    db: DBDep,
    current_user: ActiveUserDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = ScanService(db)
    scans, total = await svc.list_user_scans(
        user_id=current_user.id,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    return paginate(
        items=[ScanResponse.model_validate(s) for s in scans],
        total=total,
        page=page,
        page_size=page_size,
    )


@scans_router.get("/{scan_id}", response_model=APIResponse[ScanResponse])
@limiter.limit("60/minute")
async def get_scan(scan_id: uuid.UUID, request: Request, db: DBDep, current_user: ActiveUserDep):
    svc = ScanService(db)
    scan = await svc.get_scan(scan_id, user_id=current_user.id)
    return success_response(data=ScanResponse.model_validate(scan))


@scans_router.post("/{scan_id}/cancel", response_model=APIResponse[ScanResponse])
@limiter.limit("10/minute")
async def cancel_scan(scan_id: uuid.UUID, request: Request, db: DBDep, current_user: ActiveUserDep):
    svc = ScanService(db)
    scan = await svc.cancel_scan(scan_id, user_id=current_user.id)
    return success_response(data=ScanResponse.model_validate(scan), message="Scan cancelled.")


# ---------------------------------------------------------------------------
# Reports Router
# ---------------------------------------------------------------------------

reports_router = APIRouter(prefix="/reports", tags=["Reports"])


@reports_router.post("", response_model=APIResponse[ReportResponse], status_code=201)
@limiter.limit("10/minute")
async def create_report(payload: ReportCreate, request: Request, db: DBDep, current_user: ActiveUserDep):
    svc = ReportService(db)
    report = await svc.create_report(payload, generated_by=current_user.id)
    return success_response(data=ReportResponse.model_validate(report), message="Report generated.")


@reports_router.get("/{report_id}", response_model=APIResponse[ReportResponse])
@limiter.limit("60/minute")
async def get_report(report_id: uuid.UUID, request: Request, db: DBDep, current_user: ActiveUserDep):
    svc = ReportService(db)
    report = await svc.get_report(report_id)
    return success_response(data=ReportResponse.model_validate(report))
