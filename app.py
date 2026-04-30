from flask import Flask, render_template, request, jsonify, Response
import requests
from bs4 import BeautifulSoup
import time
import csv
import io
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LandingQAChecker/1.0)"
}

def check_url_accessible(url):
    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        elapsed = round((time.time() - start) * 1000)
        return resp, elapsed, None
    except requests.exceptions.SSLError as e:
        return None, None, f"SSL Error: {str(e)[:100]}"
    except requests.exceptions.ConnectionError as e:
        return None, None, f"Connection Error: {str(e)[:100]}"
    except requests.exceptions.Timeout:
        return None, None, "Timeout: page took too long to respond"
    except Exception as e:
        return None, None, str(e)[:100]

def check_link(base_url, href):
    try:
        full_url = urljoin(base_url, href)
        if not full_url.startswith(("http://", "https://")):
            return None
        resp = requests.head(full_url, headers=HEADERS, timeout=8, allow_redirects=True)
        if resp.status_code >= 400:
            # Try GET if HEAD fails
            resp = requests.get(full_url, headers=HEADERS, timeout=8, allow_redirects=True)
        return {"url": full_url, "status": resp.status_code, "broken": resp.status_code >= 400}
    except Exception as e:
        return {"url": full_url, "status": None, "broken": True, "error": str(e)[:60]}

def analyze_form(form, base_url):
    result = {}
    action = form.get("action", "")
    method = form.get("method", "get").lower()
    
    result["action"] = action if action else "(no action — submits to current page)"
    result["method"] = method.upper()
    result["endpoint"] = urljoin(base_url, action) if action else base_url

    inputs = form.find_all("input")
    fields = []
    has_required = False
    has_password = False
    password_via_get = False

    for inp in inputs:
        inp_type = inp.get("type", "text").lower()
        inp_name = inp.get("name", "")
        inp_required = inp.has_attr("required")
        if inp_required:
            has_required = True
        if inp_type == "password":
            has_password = True
            if method == "get":
                password_via_get = True
        if inp_type not in ("hidden", "submit", "button", "reset"):
            fields.append({
                "name": inp_name or "(unnamed)",
                "type": inp_type,
                "required": inp_required
            })

    result["fields"] = fields
    result["has_required_fields"] = has_required
    result["has_password"] = has_password
    result["password_via_get"] = password_via_get
    result["submit_buttons"] = len(form.find_all(["button", "input"], {"type": ["submit", "button"]}))

    issues = []
    if password_via_get:
        issues.append("⚠️ Password field sent via GET — credentials exposed in URL!")
    if method == "get" and has_password:
        issues.append("⚠️ Form with password uses GET method")
    if not action:
        issues.append("ℹ️ No action attribute — form submits to current page")
    if result["submit_buttons"] == 0:
        issues.append("⚠️ No submit button found in form")

    result["issues"] = issues
    return result

def run_checks(url):
    report = {"url": url, "checks": []}

    # SSL check
    parsed = urlparse(url)
    is_https = parsed.scheme == "https"
    report["checks"].append({
        "category": "Security",
        "name": "HTTPS / SSL",
        "status": "ok" if is_https else "error",
        "message": "Page uses HTTPS" if is_https else "Page uses HTTP — no SSL encryption",
        "details": None
    })

    # Accessibility + response time
    resp, elapsed, error = check_url_accessible(url)
    if error or resp is None:
        report["checks"].append({
            "category": "Availability",
            "name": "Page Accessibility",
            "status": "error",
            "message": f"Page is not accessible: {error}",
            "details": None
        })
        return report

    http_status = resp.status_code
    status_ok = 200 <= http_status < 300
    report["checks"].append({
        "category": "Availability",
        "name": "HTTP Status",
        "status": "ok" if status_ok else "error",
        "message": f"HTTP {http_status} {'OK' if status_ok else '— page returned error'}",
        "details": None
    })

    # Response time
    if elapsed < 1000:
        rt_status = "ok"
        rt_msg = f"Response time: {elapsed}ms — fast"
    elif elapsed < 3000:
        rt_status = "warning"
        rt_msg = f"Response time: {elapsed}ms — acceptable but could be faster"
    else:
        rt_status = "error"
        rt_msg = f"Response time: {elapsed}ms — too slow (>3s)"
    report["checks"].append({
        "category": "Performance",
        "name": "Response Time",
        "status": rt_status,
        "message": rt_msg,
        "details": None
    })

    # Parse HTML
    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    if not title_text:
        t_status, t_msg = "error", "Missing <title> tag"
    elif len(title_text) < 10:
        t_status, t_msg = "warning", f"Title is too short ({len(title_text)} chars): \"{title_text}\""
    elif len(title_text) > 70:
        t_status, t_msg = "warning", f"Title is too long ({len(title_text)} chars) — may be truncated in search"
    else:
        t_status, t_msg = "ok", f"Title OK ({len(title_text)} chars): \"{title_text}\""
    report["checks"].append({
        "category": "SEO",
        "name": "Title Tag",
        "status": t_status,
        "message": t_msg,
        "details": None
    })

    # Meta description
    meta_desc = soup.find("meta", {"name": re.compile("^description$", re.I)})
    desc_content = meta_desc.get("content", "").strip() if meta_desc else ""
    if not desc_content:
        d_status, d_msg = "error", "Missing meta description"
    elif len(desc_content) < 50:
        d_status, d_msg = "warning", f"Meta description too short ({len(desc_content)} chars)"
    elif len(desc_content) > 160:
        d_status, d_msg = "warning", f"Meta description too long ({len(desc_content)} chars) — may be truncated"
    else:
        d_status, d_msg = "ok", f"Meta description OK ({len(desc_content)} chars)"
    report["checks"].append({
        "category": "SEO",
        "name": "Meta Description",
        "status": d_status,
        "message": d_msg,
        "details": desc_content[:120] + "..." if len(desc_content) > 120 else desc_content or None
    })

    # H1
    h1_tags = soup.find_all("h1")
    if not h1_tags:
        h1_status, h1_msg = "error", "No <h1> tag found"
    elif len(h1_tags) > 1:
        h1_status, h1_msg = "warning", f"Multiple <h1> tags found ({len(h1_tags)}) — only one recommended"
    else:
        h1_text = h1_tags[0].get_text(strip=True)
        h1_status, h1_msg = "ok", f"H1 found: \"{h1_text[:80]}\""
    report["checks"].append({
        "category": "SEO",
        "name": "H1 Tag",
        "status": h1_status,
        "message": h1_msg,
        "details": None
    })

    # Open Graph
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")
    og_missing = []
    if not og_title: og_missing.append("og:title")
    if not og_desc: og_missing.append("og:description")
    if not og_image: og_missing.append("og:image")
    if og_missing:
        og_status = "warning"
        og_msg = f"Missing Open Graph tags: {', '.join(og_missing)}"
    else:
        og_status = "ok"
        og_msg = "All key Open Graph tags present (og:title, og:description, og:image)"
    report["checks"].append({
        "category": "SEO",
        "name": "Open Graph Tags",
        "status": og_status,
        "message": og_msg,
        "details": None
    })

    # Favicon
    favicon = soup.find("link", rel=lambda r: r and "icon" in " ".join(r).lower())
    fav_status = "ok" if favicon else "warning"
    fav_msg = "Favicon found" if favicon else "No favicon link tag found"
    report["checks"].append({
        "category": "UX",
        "name": "Favicon",
        "status": fav_status,
        "message": fav_msg,
        "details": None
    })

    # Viewport / mobile
    viewport = soup.find("meta", {"name": "viewport"})
    vp_status = "ok" if viewport else "error"
    vp_msg = f"Viewport meta tag found: \"{viewport.get('content','')}\"" if viewport else "No viewport meta tag — page may not be mobile-friendly"
    report["checks"].append({
        "category": "UX",
        "name": "Mobile Viewport",
        "status": vp_status,
        "message": vp_msg,
        "details": None
    })

    # Images without alt
    imgs = soup.find_all("img")
    no_alt = [img.get("src", "(no src)")[:80] for img in imgs if not img.get("alt")]
    if no_alt:
        img_status = "warning"
        img_msg = f"{len(no_alt)} of {len(imgs)} images missing alt attribute"
    else:
        img_status = "ok"
        img_msg = f"All {len(imgs)} images have alt attributes" if imgs else "No images found on page"
    report["checks"].append({
        "category": "Accessibility",
        "name": "Image Alt Attributes",
        "status": img_status,
        "message": img_msg,
        "details": no_alt[:5] if no_alt else None
    })

    # Broken links
    links = soup.find_all("a", href=True)
    hrefs = list(set([
        a["href"] for a in links
        if a["href"] and not a["href"].startswith(("#", "mailto:", "tel:", "javascript:"))
    ]))[:30]  # limit to 30 for speed

    broken = []
    checked_count = 0
    if hrefs:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(check_link, url, href): href for href in hrefs}
            for future in as_completed(futures):
                result = future.result()
                checked_count += 1
                if result and result.get("broken"):
                    broken.append(result["url"] + (f" [{result.get('status', 'ERR')}]"))

    if broken:
        lnk_status = "error"
        lnk_msg = f"{len(broken)} broken link(s) found out of {checked_count} checked"
    else:
        lnk_status = "ok"
        lnk_msg = f"No broken links found ({checked_count} links checked)"
    report["checks"].append({
        "category": "Links",
        "name": "Broken Links",
        "status": lnk_status,
        "message": lnk_msg,
        "details": broken[:10] if broken else None
    })

    # Forms
    forms = soup.find_all("form")
    if not forms:
        report["checks"].append({
            "category": "Forms",
            "name": "Form Detection",
            "status": "warning",
            "message": "No forms found on page",
            "details": None
        })
    else:
        form_details = []
        all_form_issues = []
        for i, form in enumerate(forms):
            fa = analyze_form(form, url)
            form_details.append(f"Form {i+1}: method={fa['method']}, action={fa['action']}, fields={len(fa['fields'])}")
            all_form_issues.extend([f"Form {i+1}: {issue}" for issue in fa["issues"]])

        if all_form_issues:
            f_status = "warning"
            f_msg = f"{len(forms)} form(s) found — {len(all_form_issues)} issue(s) detected"
        else:
            f_status = "ok"
            f_msg = f"{len(forms)} form(s) found — no critical issues"

        report["checks"].append({
            "category": "Forms",
            "name": "Form Analysis",
            "status": f_status,
            "message": f_msg,
            "details": form_details + all_form_issues if all_form_issues else form_details
        })

    # Tracking scripts
    page_source = resp.text
    tracking = {}
    tracking["GTM"] = bool(re.search(r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]+", page_source))
    tracking["GA4 / Universal Analytics"] = bool(re.search(r"googletagmanager\.com/gtag|google-analytics\.com/analytics\.js|gtag\(|ga\(", page_source))
    tracking["Meta Pixel"] = bool(re.search(r"connect\.facebook\.net|fbq\(|fbevents\.js", page_source))
    tracking["Yandex Metrica"] = bool(re.search(r"mc\.yandex\.|ym\(|metrika\.yandex", page_source))

    found = [k for k, v in tracking.items() if v]
    missing = [k for k, v in tracking.items() if not v]

    if not found:
        tr_status = "warning"
        tr_msg = "No tracking scripts detected (GTM, GA, Meta Pixel, Yandex Metrica)"
    else:
        tr_status = "ok"
        tr_msg = f"Tracking found: {', '.join(found)}"

    report["checks"].append({
        "category": "Analytics",
        "name": "Tracking Scripts",
        "status": tr_status,
        "message": tr_msg,
        "details": [f"✅ {k}" for k in found] + [f"❌ {k}" for k in missing]
    })

    # Summary
    statuses = [c["status"] for c in report["checks"]]
    report["summary"] = {
        "ok": statuses.count("ok"),
        "warning": statuses.count("warning"),
        "error": statuses.count("error"),
        "total": len(statuses)
    }

    return report


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check", methods=["POST"])
def check():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    report = run_checks(url)
    return jsonify(report)

@app.route("/export", methods=["POST"])
def export_csv():
    data = request.get_json()
    checks = data.get("checks", [])
    url = data.get("url", "")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Category", "Check", "Status", "Message", "Details"])
    for c in checks:
        details = "; ".join(c.get("details") or []) if isinstance(c.get("details"), list) else (c.get("details") or "")
        writer.writerow([c["category"], c["name"], c["status"].upper(), c["message"], details])
    output.seek(0)
    filename = f"qa_report_{urlparse(url).netloc.replace('.','_')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

if __name__ == "__main__":
    app.run(debug=True, port=5050)
