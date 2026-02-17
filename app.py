import html
import os
import random
import sqlite3
import string
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from wsgiref.simple_server import make_server

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "shorturl.db")
CODE_LENGTH = 6
MAX_GENERATION_ATTEMPTS = 10


HTML_TEMPLATE = """<!doctype html>
<html lang='en'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />
  <title>{title}</title>
  <link rel='stylesheet' href='/static/style.css' />
</head>
<body>
  <main class='container'>
    {content}
  </main>
</body>
</html>
"""


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            clicks INTEGER DEFAULT 0
        )
        """
    )
    db.commit()
    db.close()


def normalize_url(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned:
        return ""

    parsed = urlparse(cleaned)
    if not parsed.scheme:
        cleaned = f"https://{cleaned}"
        parsed = urlparse(cleaned)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    return cleaned


def generate_code() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(CODE_LENGTH))


def insert_short_url(original_url: str) -> str:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    existing = db.execute("SELECT code FROM urls WHERE original_url = ?", (original_url,)).fetchone()
    if existing:
        db.close()
        return existing["code"]

    for _ in range(MAX_GENERATION_ATTEMPTS):
        code = generate_code()
        try:
            db.execute(
                "INSERT INTO urls (code, original_url, created_at) VALUES (?, ?, ?)",
                (code, original_url, datetime.utcnow().isoformat()),
            )
            db.commit()
            db.close()
            return code
        except sqlite3.IntegrityError:
            continue

    db.close()
    raise RuntimeError("Could not generate a unique short code")


def lookup_original_url(code: str):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT original_url FROM urls WHERE code = ?", (code,)).fetchone()
    if row:
        db.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))
        db.commit()
    db.close()
    return row["original_url"] if row else None


def response(start_response, status: str, body: str, headers=None):
    payload = body.encode("utf-8")
    final_headers = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload)))]
    if headers:
        final_headers.extend(headers)
    start_response(status, final_headers)
    return [payload]


def redirect(start_response, location: str):
    start_response("302 Found", [("Location", location)])
    return [b""]


def read_css() -> bytes:
    css_path = os.path.join(BASE_DIR, "static", "style.css")
    with open(css_path, "rb") as fh:
        return fh.read()


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    if path == "/static/style.css":
        css = read_css()
        start_response("200 OK", [("Content-Type", "text/css; charset=utf-8"), ("Content-Length", str(len(css)))])
        return [css]

    if path == "/" and method == "GET":
        content = """
        <h1>Short URL</h1>
        <p class='subtitle'>Paste your long link to make it shorter in seconds.</p>
        <form method='post' class='card'>
          <label for='url'>Enter your long URL</label>
          <input id='url' name='url' type='text' placeholder='https://example.com/very/long/link' required />
          <button type='submit'>Shorten URL</button>
        </form>
        """
        return response(start_response, "200 OK", HTML_TEMPLATE.format(title="Short URL - Free URL Shortener", content=content))

    if path == "/" and method == "POST":
        size = int(environ.get("CONTENT_LENGTH") or 0)
        form_data = environ["wsgi.input"].read(size).decode("utf-8")
        form = parse_qs(form_data)
        original = normalize_url(form.get("url", [""])[0])
        if not original:
            return redirect(start_response, "/url-error.php")

        code = insert_short_url(original)
        host = environ.get("HTTP_HOST", "localhost:5000")
        scheme = environ.get("wsgi.url_scheme", "http")
        short_url = f"{scheme}://{host}/{code}"

        content = f"""
        <h1>Done! Your short URL is ready</h1>
        <div class='card result'>
          <p><strong>Original:</strong> {html.escape(original)}</p>
          <p><strong>Short:</strong> <a href='{html.escape(short_url)}'>{html.escape(short_url)}</a></p>
          <a class='btn' href='/'>Create another</a>
        </div>
        """
        return response(start_response, "200 OK", HTML_TEMPLATE.format(title="Your Short URL", content=content))

    if path == "/url-error.php":
        content = """
        <h1>Oops! Invalid URL</h1>
        <div class='card error'>
          <p>Your submitted link is not a valid HTTP or HTTPS URL.</p>
          <p>Please double-check and try again.</p>
          <a class='btn' href='/'>Go Back</a>
        </div>
        """
        return response(start_response, "400 Bad Request", HTML_TEMPLATE.format(title="Short URL - URL Error", content=content))

    code = path.lstrip("/")
    if code and "/" not in code:
        original = lookup_original_url(code)
        if original:
            return redirect(start_response, original)

    content = """
    <h1>Link Not Found</h1>
    <div class='card error'>
      <p>This short URL does not exist.</p>
      <a class='btn' href='/'>Create a new short URL</a>
    </div>
    """
    return response(start_response, "404 Not Found", HTML_TEMPLATE.format(title="Not Found", content=content))


if __name__ == "__main__":
    init_db()
    with make_server("0.0.0.0", 5000, app) as server:
        print("Serving on http://0.0.0.0:5000")
        server.serve_forever()
