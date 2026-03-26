import unittest

from kerala_psc_scraper.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)


class TestAuthSecurity(unittest.TestCase):
    def test_password_hash_and_verify(self):
        raw = "Strong#Passw0rd!"
        hashed = hash_password(raw)
        self.assertNotEqual(raw, hashed)
        self.assertTrue(verify_password(raw, hashed))
        self.assertFalse(verify_password("wrong", hashed))

    def test_password_strength_validator(self):
        self.assertTrue(validate_password_strength("Strong#Passw0rd!"))
        self.assertFalse(validate_password_strength("weakpass"))

    def test_access_token_round_trip(self):
        token = create_access_token("user-1", "user@example.com", ["customer"])
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["type"], "access")

    def test_refresh_token_round_trip(self):
        token, jti, _ = create_refresh_token("user-1")
        payload = decode_refresh_token(token)
        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["type"], "refresh")
        self.assertEqual(payload["jti"], jti)


if __name__ == "__main__":
    unittest.main()
