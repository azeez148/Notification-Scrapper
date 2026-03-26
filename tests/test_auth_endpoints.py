import os
import unittest
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+pysqlite:////tmp/notification_scrapper_auth_test.db"

from fastapi.testclient import TestClient

from kerala_psc_scraper.api.app import app, _rate_store
from kerala_psc_scraper.database.db import SessionLocal, engine
from kerala_psc_scraper.models.job_notification import Base
from kerala_psc_scraper.services.auth_service import AuthService


class TestAuthEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db = Path("/tmp/notification_scrapper_auth_test.db")
        if test_db.exists():
            test_db.unlink()
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            AuthService(db).seed_roles()
        finally:
            db.close()
        cls.client = TestClient(app)

    def setUp(self):
        _rate_store.clear()

    def test_register_login_and_profile(self):
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "customer@example.com",
                "password": "Strong#Passw0rd!",
                "name": "Customer User",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        self.assertEqual(register_response.json()["success"], True)

        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "customer@example.com", "password": "Strong#Passw0rd!"},
        )
        self.assertEqual(login_response.status_code, 200)
        body = login_response.json()["data"]
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)

        me_response = self.client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["data"]["email"], "customer@example.com")

    def test_forgot_and_reset_password(self):
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "resetuser@example.com",
                "password": "Strong#Passw0rd!",
                "name": "Reset User",
            },
        )

        forgot_response = self.client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "resetuser@example.com"},
        )
        self.assertEqual(forgot_response.status_code, 202)

        db = SessionLocal()
        try:
            service = AuthService(db)
            user = service.users.get_by_email("resetuser@example.com")
            assert user is not None
            token = service.forgot_password("resetuser@example.com")
        finally:
            db.close()
        self.assertTrue(token)

        reset_response = self.client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "N3w#StrongPassword!"},
        )
        self.assertEqual(reset_response.status_code, 200)

        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "resetuser@example.com", "password": "N3w#StrongPassword!"},
        )
        self.assertEqual(login_response.status_code, 200)

    def test_admin_role_management_access(self):
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "admin@example.com",
                "password": "Strong#Passw0rd!",
                "name": "Admin User",
            },
        )
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "target@example.com",
                "password": "Strong#Passw0rd!",
                "name": "Target User",
            },
        )

        db = SessionLocal()
        try:
            service = AuthService(db)
            admin_user = service.users.get_by_email("admin@example.com")
            assert admin_user is not None
            service.users.assign_role(admin_user, "admin")
            target_user = service.users.get_by_email("target@example.com")
            assert target_user is not None
            target_id = target_user.id
        finally:
            db.close()

        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "Strong#Passw0rd!"},
        )
        token = login_response.json()["data"]["access_token"]

        roles_response = self.client.get(
            "/api/v1/admin/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(roles_response.status_code, 200)

        update_response = self.client.patch(
            f"/api/v1/admin/users/{target_id}/role",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": "staff"},
        )
        self.assertEqual(update_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
