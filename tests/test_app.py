import io
import os
import tempfile
import unittest
from urllib.parse import urlencode

import app as shortener


class ShortUrlTests(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(delete=False)
        shortener.DB_PATH = self.tmp_db.name
        shortener.init_db()

    def tearDown(self):
        os.unlink(self.tmp_db.name)

    def request(self, path="/", method="GET", form=None):
        body = urlencode(form or {}).encode("utf-8")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
            "HTTP_HOST": "localhost:5000",
            "wsgi.url_scheme": "http",
        }
        state = {"status": "", "headers": {}}

        def start_response(status, headers):
            state["status"] = status
            state["headers"] = dict(headers)

        payload = b"".join(shortener.app(environ, start_response))
        return state["status"], state["headers"], payload

    def test_homepage(self):
        status, _, payload = self.request("/")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Paste the URL to be shortened", payload)

    def test_invalid_url_goes_to_error_page(self):
        status, headers, _ = self.request("/", method="POST", form={"url": "ftp://bad-url"})
        self.assertTrue(status.startswith("302"))
        self.assertEqual(headers.get("Location"), "/url-error.php")

    def test_valid_url_creates_shortened_url(self):
        status, _, payload = self.request("/", method="POST", form={"url": "example.com"})
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Your shortened URL", payload)

    def test_redirect_short_code(self):
        code = shortener.insert_short_url("https://example.com/page")
        status, headers, _ = self.request(f"/{code}")
        self.assertTrue(status.startswith("302"))
        self.assertEqual(headers.get("Location"), "https://example.com/page")

    def test_stats_page(self):
        shortener.insert_short_url("https://a.com")
        status, _, payload = self.request("/stats")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Total short URLs created", payload)


if __name__ == "__main__":
    unittest.main()
