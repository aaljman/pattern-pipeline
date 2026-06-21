from django.test import SimpleTestCase


class SpaServingTests(SimpleTestCase):
    def test_root_serves_built_react_application(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div id="root"></div>', html=True)
        self.assertContains(response, "/static/assets/")
