# QA Checker

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat&logo=flask&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat)

**Pre-launch QA tool for landing pages.** Paste a URL — get a full report in seconds.

> Checks SEO, accessibility, forms, broken links, tracking scripts and performance — all without touching or submitting anything on the page.

---

## What it checks

| Category | Check |
|---|---|
| 🔒 Security | HTTPS / SSL |
| 🌐 Availability | HTTP status code |
| ⚡ Performance | Response time |
| 🔍 SEO | Title, Meta Description, H1 tag |
| 📣 SEO | Open Graph tags (og:title, og:description, og:image) |
| 📱 UX | Mobile viewport, Favicon |
| ♿ Accessibility | Images missing `alt` attributes |
| 🔗 Links | Broken links (up to 30, checked in parallel) |
| 📋 Forms | Method, action endpoint, password via GET |
| 📊 Analytics | GTM, GA4, Meta Pixel, Yandex Metrica |

**Forms are never submitted.** The tool reads HTML structure only — no test leads, no fake accounts.

---

## Quick start

**Requirements:** Python 3.9+

```bash
git clone https://github.com/YOUR_USERNAME/qa-checker.git
cd qa-checker
pip3 install -r requirements.txt
python3 app.py
```

Open **http://localhost:5050** in your browser.

### macOS — one-click launch

After cloning, make the launcher executable once:

```bash
chmod +x "Запустить QA Checker.command"
```

Then just double-click `Запустить QA Checker.command` — the server starts and the browser opens automatically.

---

## Export

Click **Export CSV** after any check to download the full report as a spreadsheet-ready file.

---

## Stack

- **Backend** — Python, Flask, BeautifulSoup4, Requests
- **Frontend** — Vanilla HTML/CSS/JS, no frameworks
- **Concurrency** — `ThreadPoolExecutor` for parallel link checking

---

## License

MIT
