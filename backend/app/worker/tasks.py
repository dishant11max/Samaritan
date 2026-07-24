"""
Celery background tasks for long-running operations.
"""

from __future__ import annotations

import asyncio
import uuid

from asgiref.sync import async_to_sync

from app.core.celery_app import celery_app
from app.core.constants import ScanStatus
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.repositories import ScanRepository

logger = get_logger(__name__)


async def _execute_scan_async(scan_id_str: str) -> None:
    """Async implementation of the scan execution."""
    scan_id = uuid.UUID(scan_id_str)
    
    async with AsyncSessionLocal() as session:
        scans = ScanRepository(session)
        scan = await scans.get_by_id(scan_id)
        if not scan:
            logger.error("Scan not found for execution", extra={"scan_id": scan_id_str})
            return

        if scan.status == ScanStatus.CANCELLED:
            logger.info("Scan cancelled before execution", extra={"scan_id": scan_id_str})
            return

        # Transition to RUNNING
        scan = await scans.update_status(scan, ScanStatus.RUNNING)
        await session.commit()
        
        logger.info("Scan execution started", extra={"scan_id": scan_id_str})

    # Simulate long-running network scan operations
    await asyncio.sleep(5)
    
    async with AsyncSessionLocal() as session:
        scans = ScanRepository(session)
        scan = await scans.get_by_id(scan_id)
        
        # Check if cancelled during execution
        if scan and scan.status != ScanStatus.CANCELLED:
            # Transition to COMPLETED
            await scans.update_status(scan, ScanStatus.COMPLETED)
            await session.commit()
            logger.info("Scan execution completed", extra={"scan_id": scan_id_str})


async def _mark_scan_failed(scan_id_str: str) -> None:
    """Fallback to mark scan as failed on uncaught exception."""
    scan_id = uuid.UUID(scan_id_str)
    async with AsyncSessionLocal() as session:
        scans = ScanRepository(session)
        scan = await scans.get_by_id(scan_id)
        if scan and scan.status not in (ScanStatus.COMPLETED, ScanStatus.CANCELLED):
            await scans.update_status(scan, ScanStatus.FAILED)
            await session.commit()


@celery_app.task(bind=True, name="app.worker.tasks.execute_scan")
def execute_scan(self, scan_id_str: str) -> None:
    """
    Background task to orchestrate vulnerability scanners.
    
    Acts as a synchronous wrapper over the async DB and network calls.
    """
    try:
        async_to_sync(_execute_scan_async)(scan_id_str)
    except Exception as exc:
        logger.error("Scan execution failed", extra={"scan_id": scan_id_str}, exc_info=exc)
        async_to_sync(_mark_scan_failed)(scan_id_str)
        raise exc
