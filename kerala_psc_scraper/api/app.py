import time
from collections import defaultdict
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from kerala_psc_scraper.auth.security import decode_access_token
from kerala_psc_scraper.config.auth_settings import FORGOT_RATE_LIMIT_PER_HOUR, LOGIN_RATE_LIMIT_PER_MINUTE
from kerala_psc_scraper.database.db import get_db, init_db
from kerala_psc_scraper.services.auth_service import AuthError, AuthService

_rate_store: dict[str, list[float]] = defaultdict(list)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = next(get_db())
    try:
        AuthService(db).seed_roles()
    finally:
        db.close()
    yield


app = FastAPI(title="Notification Scraper Auth API", version="1.0.0", lifespan=lifespan)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=2, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    logout_all_devices: bool = False
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class RoleUpdateRequest(BaseModel):
    role: str


def _response(data: dict | None = None, success: bool = True, error: dict | None = None) -> dict:
    payload = {"success": success, "meta": {"request_id": "local"}}
    if success:
        payload["data"] = data or {}
    else:
        payload["error"] = error or {}
    return payload


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=_response(success=False, error=detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=_response(
            success=False,
            error={
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        ),
    )


def _apply_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    now = time.time()
    bucket = [ts for ts in _rate_store[key] if ts > now - window_seconds]
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests"},
        )
    bucket.append(now)
    _rate_store[key] = bucket


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1]


def get_current_user_payload(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    try:
        return decode_access_token(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_ACCESS_TOKEN", "message": "Invalid or expired access token"},
        ) from exc


@app.post("/api/v1/auth/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService(db).register(payload.email, payload.password, payload.name)
        return _response(
            {
                "id": user.id,
                "email": user.email,
                "name": user.full_name,
                "role": user.roles[0].name if user.roles else "customer",
                "created_at": user.created_at,
            }
        )
    except AuthError as err:
        raise HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message}) from err


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _apply_rate_limit(f"login:{request.client.host}:{payload.email.lower()}", LOGIN_RATE_LIMIT_PER_MINUTE, 60)
    try:
        result = AuthService(db).login(payload.email, payload.password, request.headers.get("user-agent"), request.client.host)
        return _response(result)
    except AuthError as err:
        raise HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message}) from err


@app.post("/api/v1/auth/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        return _response(AuthService(db).refresh(payload.refresh_token))
    except AuthError as err:
        raise HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message}) from err


@app.post("/api/v1/auth/logout")
def logout(payload: LogoutRequest, current=Depends(get_current_user_payload), db: Session = Depends(get_db)):
    AuthService(db).logout(current["sub"], payload.logout_all_devices, payload.refresh_token)
    return _response({"message": "Logged out successfully"})


@app.post("/api/v1/auth/forgot-password", status_code=202)
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    _apply_rate_limit(f"forgot:{request.client.host}:{payload.email.lower()}", FORGOT_RATE_LIMIT_PER_HOUR, 3600)
    AuthService(db).forgot_password(payload.email)
    return _response(
        {
            "message": "If an account exists, reset instructions have been sent.",
        }
    )


@app.post("/api/v1/auth/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        AuthService(db).reset_password(payload.token, payload.new_password)
        return _response({"message": "Password has been reset successfully"})
    except AuthError as err:
        raise HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message}) from err


@app.get("/api/v1/users/me")
def me(current=Depends(get_current_user_payload), db: Session = Depends(get_db)):
    user = AuthService(db).get_current_user(current["sub"])
    return _response(
        {
            "id": user.id,
            "email": user.email,
            "name": user.full_name,
            "role": user.roles[0].name if user.roles else "customer",
            "created_at": user.created_at,
        }
    )


@app.patch("/api/v1/admin/users/{user_id}/role")
def update_role(user_id: str, payload: RoleUpdateRequest, current=Depends(get_current_user_payload), db: Session = Depends(get_db)):
    try:
        AuthService(db).assign_role(current.get("roles", []), user_id, payload.role)
        return _response({"message": "Role updated"})
    except AuthError as err:
        raise HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message}) from err


@app.get("/api/v1/admin/users")
def list_users(current=Depends(get_current_user_payload), db: Session = Depends(get_db)):
    try:
        users = AuthService(db).list_users(current.get("roles", []))
        return _response({"users": users})
    except AuthError as err:
        raise HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message}) from err


@app.get("/api/v1/admin/roles")
def list_roles(current=Depends(get_current_user_payload), db: Session = Depends(get_db)):
    if "admin" not in current.get("roles", []):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Admin role required"})
    return _response({"roles": ["admin", "staff", "customer"]})
