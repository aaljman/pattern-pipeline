from unittest.mock import patch

from django.test import SimpleTestCase, TestCase


class SpaServingTests(SimpleTestCase):
    def test_root_serves_built_react_application(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div id="root"></div>', html=True)
        self.assertContains(response, "/static/assets/")


class HealthTests(TestCase):
    def test_health_checks_database_connectivity(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("datasets.views.connection.cursor", side_effect=OSError("database unavailable"))
    def test_health_fails_when_database_is_unavailable(self, _cursor):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
