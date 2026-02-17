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

    def _request(self, path="/", method="GET", form=None):
        body = b""
        if form is not None:
            body = urlencode(form).encode("utf-8")

        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
            "HTTP_HOST": "localhost:5000",
            "wsgi.url_scheme": "http",
        }

        state = {"status": None, "headers": None}

        def start_response(status, headers):
            state["status"] = status
            state["headers"] = dict(headers)

        payload = b"".join(shortener.app(environ, start_response))
        return state["status"], state["headers"], payload

    def test_home_page_loads(self):
        status, _, payload = self._request("/")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Short URL", payload)

    def test_invalid_url_redirects_to_error(self):
        status, headers, _ = self._request("/", method="POST", form={"url": "ftp://example.com/file"})
        self.assertTrue(status.startswith("302"))
        self.assertEqual(headers.get("Location"), "/url-error.php")

    def test_valid_url_creates_short_url(self):
        status, _, payload = self._request("/", method="POST", form={"url": "example.com"})
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Your short URL is ready", payload)


if __name__ == "__main__":
    unittest.main()
