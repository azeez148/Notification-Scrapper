from datetime import datetime, timezone

from sqlalchemy.orm import Session

from kerala_psc_scraper.models.auth_models import PasswordResetToken


class ResetTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, user_id: str, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        row = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_valid(self, token_hash: str) -> PasswordResetToken | None:
        now = datetime.now(timezone.utc)
        return (
            self.session.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .first()
        )

    def mark_used(self, row: PasswordResetToken) -> None:
        row.used_at = datetime.now(timezone.utc)
        self.session.commit()
