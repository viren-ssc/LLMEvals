"""Bounded official-web retrieval; no browser bypass or unsourced fallback."""

import hashlib
import io
import ipaddress
import socket
import threading
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .models import Source, digest

HOSTS = {
    "canada.ca",
    "gc.ca",
    "ourcommons.ca",
    "sencanada.ca",
    "parl.ca",
    "statcan.ca",
    "bankofcanada.ca",
    "elections.ca",
    "oag-bvg.gc.ca",
    "ontario.ca",
    "quebec.ca",
    "gouv.qc.ca",
    "gov.bc.ca",
    "alberta.ca",
    "saskatchewan.ca",
    "gov.mb.ca",
    "novascotia.ca",
    "gnb.ca",
    "gov.nl.ca",
    "princeedwardisland.ca",
    "yukon.ca",
    "gov.nt.ca",
    "gov.nu.ca",
}
MAX_BYTES = 8 * 1024 * 1024


def soft_failure(title, text):
    title = title.lower()
    body = text.lower()
    if any(
        marker in title
        for marker in (
            "page not found",
            "404 -",
            "page introuvable",
            "page cannot be found",
            "access denied",
        )
    ):
        return "Missing-page or access notice in page title"
    notices = (
        "the link you have bookmarked is no longer available",
        "the requested content is no longer available",
        "we couldn't find that web page",
        "we cannot find the page",
        "the page you are looking for has been moved",
        "la page que vous cherchez est introuvable",
        "le lien que vous avez ajouté à vos favoris n’est plus disponible",
    )
    if len(body) < 16000 and any(marker in body for marker in notices):
        return "Requested content missing or moved; HTTP 200 is not substantive evidence"
    if len(body) < 8000 and any(
        marker in body
        for marker in ("verify you are human", "enable javascript and cookies to continue")
    ):
        return "Bot/access challenge rather than source content"
    return ""


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.title_parts = [], []
        self.skip = 0
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if not self.skip and tag in {"p", "div", "li", "br", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False
        if not self.skip and tag in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if not self.skip:
            self.parts.append(data)


def extract(raw, content_type):
    if "pdf" in content_type or raw.startswith(b"%PDF"):
        from pypdf import PdfReader

        pages = PdfReader(io.BytesIO(raw)).pages
        if len(pages) > 300:
            raise ValueError("PDF exceeds 300-page retrieval limit")
        return "PDF document", "\n".join(
            f"[Page {i}]\n{page.extract_text() or ''}" for i, page in enumerate(pages, 1)
        )
    if "html" in content_type:
        parser = TextParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
        text = "\n".join(
            f"[L{i:05d}] {line}" for i, line in enumerate((line for line in lines if line), 1)
        )
        return " ".join(parser.title_parts).strip(), text
    if content_type.startswith("text/plain"):
        return "Text document", "\n".join(
            f"[L{i:05d}] {line}"
            for i, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1)
        )
    raise ValueError("Unsupported source format; configure another retrieval adapter")


class SourceRetriever:
    def __init__(self, db, config, transport=None, sleep=time.sleep, resolve=True):
        self.db, self.config, self.sleep, self.resolve = db, config, sleep, resolve
        self.config.cache.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            timeout=config.source_timeout,
            transport=transport,
            follow_redirects=False,
            headers={"User-Agent": config.contact},
            verify=True,
        )
        self.guard = threading.Lock()
        self.locks, self.robots, self.last = {}, {}, {}

    def close(self):
        self.client.close()

    def authoritative(self, url):
        host = (urlsplit(url).hostname or "").lower()
        return any(
            host == h or host.endswith("." + h)
            for h in HOSTS | set(self.config.extra_authority_hosts)
        )

    def validate_url(self, url):
        p = urlsplit(url)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            raise ValueError("Invalid public source URL")
        if p.port not in (None, 80, 443) or not self.authoritative(url):
            raise ValueError("Source host is not on the configured authority allowlist")
        if self.resolve:
            addresses = socket.getaddrinfo(p.hostname, p.port or 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ValueError("Nonpublic source address refused")

    def request(self, url):
        self.validate_url(url)
        for attempt in range(self.config.attempts):
            try:
                with self.client.stream("GET", url) as response:
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError("Source exceeds 8 MiB limit")
                        chunks.append(chunk)
                    result = httpx.Response(
                        response.status_code,
                        # iter_bytes() already decodes Content-Encoding. Preserve metadata
                        # except compression/length headers to avoid decoding the body twice.
                        headers={
                            k: v
                            for k, v in response.headers.items()
                            if k.lower() not in {"content-encoding", "content-length"}
                        },
                        content=b"".join(chunks),
                        request=response.request,
                    )
                if result.status_code != 429 and result.status_code < 500:
                    return result
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == self.config.attempts - 1:
                    raise
            if attempt < self.config.attempts - 1:
                delay = 2**attempt
                if "result" in locals():
                    retry_after = result.headers.get("Retry-After", "")
                    if retry_after.isdigit():
                        delay = max(delay, min(int(retry_after), 60))
                self.sleep(delay)
        return result

    def allowed(self, url):
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.robots:
            r = self.request(origin + "/robots.txt")
            for _ in range(3):
                if r.status_code not in {301, 302, 303, 307, 308}:
                    break
                target = urljoin(str(r.request.url), r.headers.get("location", ""))
                if (
                    urlsplit(str(r.request.url)).scheme == "https"
                    and urlsplit(target).scheme != "https"
                ):
                    return False, 1.0
                r = self.request(target)
            parser = RobotFileParser()
            if r.status_code == 404:
                parser.parse(["User-agent: *", "Disallow:"])
            elif r.status_code == 200:
                parser.parse(r.text.splitlines())
            else:
                return False, 1.0
            self.robots[origin] = parser
        parser = self.robots[origin]
        delay = max(float(parser.crawl_delay(self.config.contact) or 1), 1.0)
        rate = parser.request_rate(self.config.contact)
        if rate:
            delay = max(delay, rate.seconds / rate.requests)
        return parser.can_fetch(self.config.contact, url), delay

    def fetch(self, url):
        with self.guard:
            lock = self.locks.setdefault(url, threading.Lock())
        with lock:
            cached = self.db.source_get("web:" + digest(url))
            if cached:
                age = (
                    datetime.now(timezone.utc) - datetime.fromisoformat(cached.retrieved_at)
                ).total_seconds()
                ttl = self.config.source_ttl_hours * 3600 if cached.status == "ok" else 60
                raw = Path(cached.raw_path)
                intact = cached.status != "ok" or (
                    raw.is_file() and hashlib.sha256(raw.read_bytes()).hexdigest() == cached.sha256
                )
                if age < ttl and intact:
                    if cached.status == "ok" and (
                        reason := soft_failure(cached.title, cached.text)
                    ):
                        cached.status, cached.error = "soft_failed", reason
                        self.db.source_put("web:" + digest(url), cached)
                    return cached
            try:
                current = url
                for _ in range(6):
                    self.validate_url(current)
                    host = urlsplit(current).netloc
                    with self.guard:
                        host_lock = self.locks.setdefault("host:" + host, threading.Lock())
                    with host_lock:
                        allowed, delay = self.allowed(current)
                        if not allowed:
                            source = Source(
                                url=url,
                                final_url=current,
                                status="blocked",
                                error="robots.txt prohibits access or could not be established",
                            )
                            break
                        self.sleep(max(0, self.last.get(host, 0) + delay - time.monotonic()))
                        r = self.request(current)
                        self.last[host] = time.monotonic()
                    if r.status_code in {301, 302, 303, 307, 308}:
                        target = urljoin(current, r.headers.get("location", ""))
                        if (
                            urlsplit(current).scheme == "https"
                            and urlsplit(target).scheme != "https"
                        ):
                            raise ValueError("HTTPS downgrade refused")
                        current = target
                        continue
                    if r.status_code != 200:
                        source = Source(
                            url=url,
                            final_url=current,
                            status="blocked" if r.status_code in {401, 403, 429} else "failed",
                            error=f"HTTP {r.status_code}; no factual verdict inferred",
                        )
                        break
                    sha = hashlib.sha256(r.content).hexdigest()
                    raw_path = self.config.cache / (sha + ".raw")
                    raw_path.write_bytes(r.content)
                    try:
                        title, text = extract(r.content, r.headers.get("content-type", ""))
                    except ValueError as exc:
                        source = Source(
                            url=url,
                            final_url=current,
                            status="unsupported_format",
                            sha256=sha,
                            raw_path=str(raw_path.resolve()),
                            error=str(exc),
                        )
                    else:
                        if not text.strip():
                            raise ValueError(
                                "No readable source text; OCR or browser adapter required"
                            )
                        source = Source(
                            url=url,
                            final_url=current,
                            title=title,
                            text=text,
                            status="ok",
                            sha256=sha,
                            raw_path=str(raw_path.resolve()),
                            authoritative=self.authoritative(current),
                        )
                        if reason := soft_failure(title, text):
                            source.status, source.error = "soft_failed", reason
                    break
                else:
                    raise ValueError("Too many source redirects")
            except Exception as exc:
                source = Source(
                    url=url,
                    status="failed",
                    error=(str(exc) if isinstance(exc, ValueError) else type(exc).__name__),
                )
            self.db.source_put("web:" + digest(url), source)
            return source

    def import_warc(self, path):
        """Retain entire original WARC and dated response records; never replace current web evidence."""
        from warcio.archiveiterator import ArchiveIterator

        raw = path.read_bytes()
        archive_sha = hashlib.sha256(raw).hexdigest()
        archive_path = self.config.cache / (archive_sha + ".warc")
        archive_path.write_bytes(raw)
        count = 0
        with path.open("rb") as f:
            for record in ArchiveIterator(f):
                if record.rec_type != "response" or not record.http_headers:
                    continue
                if record.http_headers.get_statuscode() != "200":
                    continue
                url = record.rec_headers.get_header("WARC-Target-URI")
                if not url or not self.authoritative(url):
                    continue
                body = record.content_stream().read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    continue
                try:
                    title, text = extract(
                        body, record.http_headers.get_header("Content-Type") or ""
                    )
                except ValueError:
                    continue
                captured = record.rec_headers.get_header("WARC-Date") or ""
                body_sha = hashlib.sha256(body).hexdigest()
                body_path = self.config.cache / (body_sha + ".raw")
                body_path.write_bytes(body)
                source = Source(
                    url=url,
                    final_url=url,
                    title=title,
                    text=text,
                    status="ok",
                    authoritative=True,
                    historical=True,
                    archive_date=captured,
                    archive_container_path=str(archive_path.resolve()),
                    archive_container_sha256=archive_sha,
                    archive_record_id=record.rec_headers.get_header("WARC-Record-ID") or "",
                    sha256=body_sha,
                    raw_path=str(body_path.resolve()),
                )
                self.db.source_put("warc:" + digest([url, captured, body_sha]), source)
                count += 1
        return count
