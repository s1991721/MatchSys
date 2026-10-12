from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings

from . import credentials
from .middleware import COOKIE_NAME
from django.contrib.sessions.backends.file import SessionStore


class PlatformLoginTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(SESSION_FILE_PATH=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        storage = patch.object(SessionStore, "_storage_path", directory.name, create=True)
        storage.start()
        self.addCleanup(storage.stop)

    def login(self, client=None):
        return (client or self.client).post("/tenant-management/login/", {
            "username": credentials.ADMIN_USERNAME, "password": "MatchSys@2026",
        })

    def test_login_and_dashboard_do_not_access_database(self):
        self.assertEqual(self.client.get("/tenant-management/login/").status_code, 200)
        self.assertRedirects(self.login(), "/tenant-management/")
        self.assertIn(COOKIE_NAME, self.client.cookies)
        self.assertNotIn("sessionid", self.client.cookies)
        self.assertContains(self.client.get("/tenant-management/"), "平台管理员已登录")

    def test_protection_invalid_password_and_logout(self):
        self.assertRedirects(self.client.get("/tenant-management/"), "/tenant-management/login/")
        response = self.client.post("/tenant-management/login/", {
            "username": credentials.ADMIN_USERNAME, "password": "wrong",
        })
        self.assertContains(response, "账号或密码错误")
        self.login()
        old_cookie = self.client.cookies[COOKIE_NAME].value
        self.assertEqual(self.client.get("/tenant-management/logout/").status_code, 405)
        self.assertRedirects(self.client.post("/tenant-management/logout/"), "/tenant-management/login/")
        replay = Client()
        replay.cookies[COOKIE_NAME] = old_cookie
        self.assertRedirects(replay.get("/tenant-management/"), "/tenant-management/login/")

    def test_csrf_required_and_credentials_change_invalidates_session(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.login(client).status_code, 403)
        client.get("/tenant-management/login/")
        response = client.post("/tenant-management/login/", {
            "username": credentials.ADMIN_USERNAME, "password": "MatchSys@2026",
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)
        with patch.object(credentials, "ADMIN_USERNAME", "changed"):
            self.assertRedirects(client.get("/tenant-management/"), "/tenant-management/login/")
