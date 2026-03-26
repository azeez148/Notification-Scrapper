from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from kerala_psc_scraper.config.auth_settings import ACCOUNT_LOCK_DURATION_MINUTES, ACCOUNT_LOCK_THRESHOLD
from kerala_psc_scraper.models.auth_models import Role, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_email(self, email: str) -> User | None:
        return self.session.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: str) -> User | None:
        return self.session.query(User).filter(User.id == user_id).first()

    def list_users(self) -> list[User]:
        return self.session.query(User).all()

    def create(self, email: str, password_hash: str, full_name: str, role_name: str = "customer") -> User:
        role = self.session.query(Role).filter(Role.name == role_name).first()
        user = User(email=email, password_hash=password_hash, full_name=full_name)
        if role is not None:
            user.roles.append(role)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def ensure_default_roles(self) -> None:
        for role_name in ("admin", "staff", "customer"):
            exists = self.session.query(Role).filter(Role.name == role_name).first()
            if not exists:
                self.session.add(Role(name=role_name))
        self.session.commit()

    def increment_failed_login(self, user: User) -> None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= ACCOUNT_LOCK_THRESHOLD:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=ACCOUNT_LOCK_DURATION_MINUTES)
        self.session.commit()

    def reset_failed_login(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
        self.session.commit()

    def update_password_hash(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        self.session.commit()

    def assign_role(self, user: User, role_name: str) -> None:
        role = self.session.query(Role).filter(Role.name == role_name).first()
        if role is None:
            role = Role(name=role_name)
            self.session.add(role)
            self.session.flush()
        user.roles = [role]
        self.session.commit()
