# Short URL Website (100% GitHub-friendly)

This is a complete short URL web app that works without third-party Python packages.

## What is implemented

- Home page to create short URLs.
- URL validation and `/url-error.php` flow.
- Automatic short code generation with SQLite persistence.
- Redirects from short code to original URL.
- Stats page (`/stats`) and custom 404 page.
- Works with local run and platform deploys that provide a `PORT` env variable.

## Run locally

```bash
python3 app.py
```

Then open:

- `http://localhost:5000`

## Run tests

```bash
python3 -m unittest discover -s tests
```

## Deploy from GitHub

Any platform that can run Python apps and expose a port can deploy this project.

Start command:

```bash
python3 app.py
```

The app reads `PORT` automatically when provided by hosting platforms.
