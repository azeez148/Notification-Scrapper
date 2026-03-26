from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kerala_psc_scraper.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_secure_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)
from kerala_psc_scraper.config.auth_settings import PASSWORD_RESET_TTL_MINUTES
from kerala_psc_scraper.database.reset_token_repository import ResetTokenRepository
from kerala_psc_scraper.database.session_repository import SessionRepository
from kerala_psc_scraper.database.user_repository import UserRepository
from kerala_psc_scraper.models.auth_models import User


class AuthError(Exception):
    def __init__(self, code: str, status_code: int, message: str):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)
        self.reset_tokens = ResetTokenRepository(session)

    def seed_roles(self) -> None:
        self.users.ensure_default_roles()

    @staticmethod
    def _user_roles(user: User) -> list[str]:
        return [role.name for role in user.roles] if user.roles else ["customer"]

    def register(self, email: str, password: str, name: str) -> User:
        if not validate_password_strength(password):
            raise AuthError("WEAK_PASSWORD", 400, "Password does not meet strength requirements")
        try:
            return self.users.create(email=email.lower().strip(), password_hash=hash_password(password), full_name=name.strip())
        except IntegrityError:
            self.session.rollback()
            raise AuthError("EMAIL_ALREADY_EXISTS", 409, "Email already exists")

    def login(self, email: str, password: str, user_agent: str | None, ip_address: str | None) -> dict:
        now = datetime.now(timezone.utc)
        user = self.users.get_by_email(email.lower().strip())
        if not user or not verify_password(password, user.password_hash):
            if user:
                self.users.increment_failed_login(user)
            raise AuthError("INVALID_CREDENTIALS", 401, "Email or password is incorrect")

        if user.locked_until and user.locked_until > now:
            raise AuthError("ACCOUNT_LOCKED", 423, "Account is temporarily locked")

        self.users.reset_failed_login(user)
        access_token = create_access_token(user.id, user.email, self._user_roles(user))
        refresh_token, refresh_jti, refresh_expires = create_refresh_token(user.id)
        self.sessions.create(
            user_id=user.id,
            refresh_jti_hash=hash_token(refresh_jti),
            expires_at=refresh_expires,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": 900,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.full_name,
                "role": self._user_roles(user)[0],
                "created_at": user.created_at,
            },
        }

    def refresh(self, refresh_token: str) -> dict:
        try:
            payload = decode_refresh_token(refresh_token)
        except jwt.InvalidTokenError as exc:
            raise AuthError("INVALID_REFRESH_TOKEN", 401, "Invalid refresh token") from exc

        jti = payload.get("jti")
        user_id = payload.get("sub")
        if not jti or not user_id:
            raise AuthError("INVALID_REFRESH_TOKEN", 401, "Invalid refresh token")

        old_hash = hash_token(jti)
        active_session = self.sessions.get_active_by_hash(old_hash)
        if not active_session:
            raise AuthError("EXPIRED_REFRESH_TOKEN", 401, "Refresh token expired or revoked")

        user = self.users.get_by_id(user_id)
        if not user:
            raise AuthError("USER_NOT_FOUND", 404, "User not found")

        self.sessions.revoke_by_hash(old_hash)
        new_refresh_token, new_jti, new_expires = create_refresh_token(user.id)
        self.sessions.create(user.id, hash_token(new_jti), new_expires, active_session.user_agent, active_session.ip_address)
        access_token = create_access_token(user.id, user.email, self._user_roles(user))
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "Bearer",
            "expires_in": 900,
        }

    def logout(self, user_id: str, logout_all_devices: bool, refresh_token: str | None = None) -> None:
        if logout_all_devices:
            self.sessions.revoke_all_for_user(user_id)
            return

        if refresh_token:
            try:
                payload = decode_refresh_token(refresh_token)
            except jwt.InvalidTokenError:
                return
            jti = payload.get("jti")
            if jti:
                self.sessions.revoke_by_hash(hash_token(jti))

    def forgot_password(self, email: str) -> str | None:
        user = self.users.get_by_email(email.lower().strip())
        if not user:
            return None

        raw = generate_secure_token()
        token_hash = hash_token(raw)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
        self.reset_tokens.create(user.id, token_hash, expires_at)
        return raw

    def reset_password(self, token: str, new_password: str) -> None:
        if not validate_password_strength(new_password):
            raise AuthError("WEAK_PASSWORD", 400, "Password does not meet strength requirements")

        row = self.reset_tokens.get_valid(hash_token(token))
        if not row:
            raise AuthError("INVALID_RESET_TOKEN", 401, "Invalid or expired reset token")

        user = self.users.get_by_id(row.user_id)
        if not user:
            raise AuthError("USER_NOT_FOUND", 404, "User not found")

        self.users.update_password_hash(user, hash_password(new_password))
        self.reset_tokens.mark_used(row)
        self.sessions.revoke_all_for_user(user.id)

    def get_current_user(self, user_id: str) -> User:
        user = self.users.get_by_id(user_id)
        if not user:
            raise AuthError("USER_NOT_FOUND", 404, "User not found")
        return user

    def list_users(self, actor_roles: list[str]) -> list[dict]:
        if "admin" not in actor_roles:
            raise AuthError("FORBIDDEN", 403, "Admin role required")
        users = self.users.list_users()
        return [
            {
                "id": user.id,
                "email": user.email,
                "name": user.full_name,
                "role": self._user_roles(user)[0],
                "created_at": user.created_at,
            }
            for user in users
        ]

    def assign_role(self, actor_roles: list[str], user_id: str, role: str) -> None:
        if "admin" not in actor_roles:
            raise AuthError("FORBIDDEN", 403, "Admin role required")
        user = self.users.get_by_id(user_id)
        if not user:
            raise AuthError("USER_NOT_FOUND", 404, "User not found")
        self.users.assign_role(user, role)
