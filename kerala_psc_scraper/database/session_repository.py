from datetime import datetime, timezone

from sqlalchemy.orm import Session

from kerala_psc_scraper.models.auth_models import AuthSession


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, user_id: str, refresh_jti_hash: str, expires_at: datetime, user_agent: str | None, ip_address: str | None) -> AuthSession:
        auth_session = AuthSession(
            user_id=user_id,
            refresh_jti_hash=refresh_jti_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.session.add(auth_session)
        self.session.commit()
        self.session.refresh(auth_session)
        return auth_session

    def get_active_by_hash(self, refresh_jti_hash: str) -> AuthSession | None:
        now = datetime.now(timezone.utc)
        return (
            self.session.query(AuthSession)
            .filter(
                AuthSession.refresh_jti_hash == refresh_jti_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .first()
        )

    def revoke_by_hash(self, refresh_jti_hash: str) -> None:
        auth_session = self.session.query(AuthSession).filter(AuthSession.refresh_jti_hash == refresh_jti_hash).first()
        if auth_session and auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(timezone.utc)
            self.session.commit()

    def revoke_all_for_user(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)
        rows = self.session.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).all()
        for row in rows:
            row.revoked_at = now
        self.session.commit()
