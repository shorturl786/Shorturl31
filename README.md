# Short URL Website

A complete URL shortener web app built with Python WSGI and SQLite.

## Features

- Create short links from long URLs
- `http`/`https` URL validation
- `url-error.php` page for invalid links
- Redirect support for short codes
- 404 page for missing short URLs
- Automatic reuse of existing code for duplicate long URLs

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open: `http://localhost:5000`

## Run tests

```bash
python -m unittest discover -s tests
```
