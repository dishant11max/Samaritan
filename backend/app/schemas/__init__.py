"""schemas package."""

from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse, PaginationMeta
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.target import TargetCreate, TargetResponse, TargetUpdate
from app.schemas.scan import ScanCreate, ScanResponse, ScanResultResponse
from app.schemas.report import ReportCreate, ReportResponse

__all__ = [
    "APIResponse", "ErrorResponse", "PaginatedResponse", "PaginationMeta",
    "LoginRequest", "RegisterRequest", "TokenResponse",
    "UserCreate", "UserResponse", "UserUpdate",
    "TargetCreate", "TargetResponse", "TargetUpdate",
    "ScanCreate", "ScanResponse", "ScanResultResponse",
    "ReportCreate", "ReportResponse",
]
