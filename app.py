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
MAX_GENERATION_ATTEMPTS = 20


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_urls_code ON urls(code)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_urls_original ON urls(original_url)")


def normalize_url(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned:
        return ""

    parsed = urlparse(cleaned)
    if not parsed.scheme:
        cleaned = f"https://{cleaned}"
        parsed = urlparse(cleaned)

    if parsed.scheme not in {"http", "https"}:
        return ""

    if not parsed.netloc or " " in cleaned:
        return ""

    return cleaned


def generate_code() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(CODE_LENGTH))


def insert_short_url(original_url: str) -> str:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        existing = db.execute(
            "SELECT code FROM urls WHERE original_url = ?",
            (original_url,),
        ).fetchone()
        if existing:
            return existing["code"]

        for _ in range(MAX_GENERATION_ATTEMPTS):
            code = generate_code()
            try:
                db.execute(
                    "INSERT INTO urls (code, original_url, created_at) VALUES (?, ?, ?)",
                    (code, original_url, datetime.utcnow().isoformat()),
                )
                return code
            except sqlite3.IntegrityError:
                continue

    raise RuntimeError("Could not generate a unique short code")


def lookup_original_url(code: str):
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT original_url FROM urls WHERE code = ?", (code,)).fetchone()
        if row:
            db.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))
            return row["original_url"]
    return None


def count_urls() -> int:
    with sqlite3.connect(DB_PATH) as db:
        result = db.execute("SELECT COUNT(*) AS total FROM urls").fetchone()
        return int(result[0])


def html_page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='UTF-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>{html.escape(title)}</title>
  <link rel='stylesheet' href='/static/style.css'>
</head>
<body>
  <header class='topbar'>
    <a href='/' class='brand'>shorturl.at clone</a>
    <a href='/stats' class='nav-link'>Stats</a>
  </header>
  <main class='container'>
    {content}
  </main>
  <footer class='footer'>Made for 100% working GitHub deploy use-case.</footer>
</body>
</html>"""


def text_response(start_response, status: str, payload: bytes, content_type: str, extra_headers=None):
    headers = [("Content-Type", content_type), ("Content-Length", str(len(payload)))]
    if extra_headers:
        headers.extend(extra_headers)
    start_response(status, headers)
    return [payload]


def html_response(start_response, status: str, body: str):
    return text_response(start_response, status, body.encode("utf-8"), "text/html; charset=utf-8")


def do_redirect(start_response, location: str):
    start_response("302 Found", [("Location", location), ("Content-Length", "0")])
    return [b""]


def parse_form(environ) -> dict:
    length = int(environ.get("CONTENT_LENGTH") or "0")
    body = environ.get("wsgi.input").read(length).decode("utf-8") if length > 0 else ""
    parsed = parse_qs(body)
    return {key: values[0] if values else "" for key, values in parsed.items()}


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if path == "/static/style.css":
        css_path = os.path.join(BASE_DIR, "static", "style.css")
        with open(css_path, "rb") as fh:
            payload = fh.read()
        return text_response(start_response, "200 OK", payload, "text/css; charset=utf-8")

    if path == "/" and method == "GET":
        content = """
<section class='hero'>
  <h1>Paste the URL to be shortened</h1>
  <p>Simple, fast, and reliable short link service.</p>
</section>
<form method='post' class='card form-card'>
  <input id='url' name='url' type='text' placeholder='Enter the link here' required>
  <button type='submit'>Shorten URL</button>
</form>
<p class='helper'>Example valid input: <code>https://example.com</code> or <code>example.com/page</code></p>
"""
        return html_response(start_response, "200 OK", html_page("Free URL Shortener", content))

    if path == "/" and method == "POST":
        form = parse_form(environ)
        original = normalize_url(form.get("url", ""))
        if not original:
            return do_redirect(start_response, "/url-error.php")

        code = insert_short_url(original)
        host = environ.get("HTTP_HOST", "localhost:5000")
        scheme = environ.get("wsgi.url_scheme", "http")
        short_url = f"{scheme}://{host}/{code}"

        content = f"""
<section class='hero'>
  <h1>Your shortened URL</h1>
</section>
<div class='card result-card'>
  <p><strong>Original URL:</strong> {html.escape(original)}</p>
  <p><strong>Short URL:</strong> <a href='{html.escape(short_url)}'>{html.escape(short_url)}</a></p>
  <div class='actions'>
    <a class='btn secondary' href='/'>Create another</a>
  </div>
</div>
"""
        return html_response(start_response, "200 OK", html_page("Your short URL", content))

    if path == "/url-error.php":
        content = """
<section class='hero'>
  <h1>Invalid URL</h1>
</section>
<div class='card error-card'>
  <p>The URL you entered is not valid.</p>
  <p>Please make sure it starts with <code>http://</code> or <code>https://</code> (or include a valid domain name).</p>
  <a class='btn' href='/'>Try Again</a>
</div>
"""
        return html_response(start_response, "400 Bad Request", html_page("URL error", content))

    if path == "/stats":
        total = count_urls()
        content = f"""
<section class='hero'>
  <h1>Service Stats</h1>
</section>
<div class='card'>
  <p>Total short URLs created: <strong>{total}</strong></p>
  <a class='btn secondary' href='/'>Back to shortener</a>
</div>
"""
        return html_response(start_response, "200 OK", html_page("Stats", content))

    code = path.lstrip("/")
    if code and "/" not in code:
        target = lookup_original_url(code)
        if target:
            return do_redirect(start_response, target)

    content = """
<section class='hero'>
  <h1>404 - Link not found</h1>
</section>
<div class='card error-card'>
  <p>This short URL does not exist or has expired.</p>
  <a class='btn' href='/'>Create new short URL</a>
</div>
"""
    return html_response(start_response, "404 Not Found", html_page("404 Not Found", content))


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "5000"))
    with make_server("0.0.0.0", port, app) as server:
        print(f"Serving on http://0.0.0.0:{port}")
        server.serve_forever()
