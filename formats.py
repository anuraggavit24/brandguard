"""Content formats other than video and audio: posters, banners, images, documents and web pages (blogs).

Each format is turned into text lines in the same shape the checker already uses for on-screen text
({"start", "end", "text", "raw", "conf"}), so prices, banned phrases, product facts and the AI reviewer all work on it.
Images also keep the position and height of each line for the brand-asset and accessibility checks (assets.py).
"""

import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import ocr

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
DOC_EXT = {".pdf", ".docx", ".txt"}
PAGE_MAX_BYTES = 2 * 1024 * 1024
MAX_LINES = 400


def kind_of(path):
    ext = Path(str(path)).suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in DOC_EXT:
        return "document"
    return "video"


def _split(text):
    out = []
    for block in re.split(r"\n\s*\n|\r\n\r\n", text or ""):
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        for s in re.split(r"(?<=[.!?।])\s+", block):
            s = s.strip()
            if len(s) >= 2:
                out.append(s[:600])
    return out[:MAX_LINES]


def lines_from_text(text):
    return [{"start": 0, "end": 0, "text": ocr.normalise(s), "raw": s, "conf": 1.0} for s in _split(text)]


def read_document(path):
    """Text lines of a PDF, Word or text file. Raises ValueError with a clear message."""
    import importer
    p = Path(path)
    text = importer.extract_text(p.name, p.read_bytes())
    lines = lines_from_text(text)
    if not lines:
        raise ValueError("No text was found in this document.")
    return lines


def read_image(path):
    """OCR lines of a poster or banner, or None when OCR is unavailable."""
    return ocr.read_image(path)


# ------------------------------------------------------------------ web pages and blogs
class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe", "template"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "section", "article", "blockquote", "td"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.title, self.in_title, self.desc = [], 0, "", False, ""

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            a = dict(attrs)
            if (a.get("name") or a.get("property") or "").lower() in ("description", "og:description") and a.get("content"):
                self.desc = self.desc or a["content"]
        if tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def public_host(host):
    """True only if every address of the host is a public internet address (blocks localhost and internal networks)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            return False
    return True


def fetch_page(url, getter=None):
    """Download a public web page and return (title, description, text). Raises ValueError with a clear message.
    Only http/https, only public addresses (checked again on every redirect), at most 2 MB, HTML or plain text."""
    import requests
    getter = getter or requests.get
    for _ in range(4):
        p = urlparse((url or "").strip())
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ValueError("Paste a full web address starting with http:// or https://.")
        if not public_host(p.hostname):
            raise ValueError("That address is not a public web page.")
        try:
            r = getter(url, timeout=15, allow_redirects=False, stream=True,
                       headers={"User-Agent": "BrandGuard content review (+compliance check)"})
        except Exception:
            raise ValueError("The page could not be reached.")
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            url = urljoin(url, r.headers["location"])
            continue
        if r.status_code != 200:
            raise ValueError(f"The page answered with an error ({r.status_code}).")
        ctype = (r.headers.get("content-type") or "").lower()
        if not ("html" in ctype or "text/plain" in ctype):
            raise ValueError("That link is not a web page. Upload the file instead.")
        data = b""
        for chunk in r.iter_content(65536):
            data += chunk
            if len(data) > PAGE_MAX_BYTES:
                raise ValueError("The page is too large to review.")
        enc = r.encoding or "utf-8"
        raw = data.decode(enc, errors="replace")
        if "html" not in ctype:
            return "", "", raw
        t = _Text()
        t.feed(raw)
        text = html.unescape("".join(t.parts))
        return re.sub(r"\s+", " ", t.title).strip()[:200], t.desc.strip()[:500], text
    raise ValueError("The page redirected too many times.")
