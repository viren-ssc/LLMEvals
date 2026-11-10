"""Observed official links and recorded/live search results, never model-invented URLs."""

import json
import os
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from dotenv import dotenv_values

from .evidence import tokens
from .models import Record, now


class DiscoveryResult(Record):
    sources: list
    log: list[dict]


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.target, self.text = [], "", []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.target, self.text = attrs.get("href", ""), []
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
            content = attrs.get("content", "")
            if "url=" in content.lower():
                self.links.append((content.split("=", 1)[1].strip(" '\""), "moved content"))

    def handle_data(self, text):
        if self.target:
            self.text.append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self.target:
            self.links.append((self.target, "".join(self.text)))
            self.target = ""


class Discovery:
    def __init__(self, retriever, index=None):
        self.retriever = retriever
        self.index = json.loads(index.read_text(encoding="utf-8")) if index else []
        self.settings = {**dotenv_values(".env"), **os.environ}

    def live_search(self, query, log):
        key = self.settings.get("BRAVE_SEARCH_API_KEY")
        if not key:
            log.append(
                {
                    "method": "live_search",
                    "status": "not_configured",
                    "limitation": "No live search API key; using recorded search index and official links",
                }
            )
            return []
        for attempt in range(3):
            try:
                response = httpx.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query + " (site:gc.ca OR site:canada.ca)", "count": 8},
                    headers={"X-Subscription-Token": key},
                    timeout=25,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < 2:
                        time.sleep(2**attempt)
                        continue
                response.raise_for_status()
                urls = [r["url"] for r in response.json().get("web", {}).get("results", [])]
                log.append({"method": "brave_search", "query": query, "urls": urls, "at": now()})
                return urls
            except (httpx.HTTPError, ValueError, KeyError):
                if attempt == 2:
                    log.append({"method": "live_search", "status": "failed", "query": query})
        return []

    def observed_links(self, source, query):
        if not source.raw_path or not Path(source.raw_path).is_file():
            return []
        parser = LinkParser()
        parser.feed(Path(source.raw_path).read_bytes().decode("utf-8", errors="replace"))
        ranked = []
        for href, label in parser.links:
            url = urljoin(source.final_url or source.url, href).split("#")[0]
            if urlsplit(url).scheme != "https" or not self.retriever.authoritative(url):
                continue
            overlap = len(tokens(query) & tokens(label + " " + url))
            if overlap or label == "moved content":
                ranked.append((overlap + 5 * (label == "moved content"), url))
        return list(dict.fromkeys(u for _, u in sorted(ranked, reverse=True)))[:3]

    def collect(self, question, extra_urls=()):
        log, sources, seen = [], [], set()

        def fetch(url, method, **detail):
            if url in seen:
                return None
            seen.add(url)
            source = self.retriever.fetch(url)
            sources.append(source)
            log.append(
                {"method": method, "url": url, "status": source.status, "at": now(), **detail}
            )
            return source

        failed = []
        for url in question.source_urls:
            source = fetch(url, "original_url")
            if source and source.status != "ok":
                failed.append(source)
        # Search provenance stays separate from evidence; every discovered target must be retrieved.
        entries = [row for row in self.index if row.get("question_id") == question.question_id]
        for row in entries:
            fetch(
                row["url"],
                "recorded_search",
                query=row.get("query", ""),
                provider=row.get("provider", ""),
                searched_at=row.get("searched_at", ""),
            )
        for url in extra_urls:
            fetch(url, "explicit_primary_source")
        if failed:
            for url in self.live_search(question.question, log):
                if self.retriever.authoritative(url):
                    fetch(url, "live_search_result")
            for source in failed:
                for url in self.observed_links(source, question.question):
                    fetch(url, "observed_migration_link", old_url=source.url)
        # Follow highly relevant official document links when search produced no substantive content.
        if not any(s.status == "ok" for s in sources):
            log.append(
                {
                    "method": "discovery",
                    "status": "needs_more_evidence",
                    "limitation": "No substantive authoritative source; no unsourced fallback",
                }
            )
        unique = {(s.final_url or s.url, s.sha256, s.historical): s for s in sources}
        return DiscoveryResult(sources=[s.model_dump() for s in unique.values()], log=log)
