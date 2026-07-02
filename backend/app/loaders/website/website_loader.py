"""
Loader for public website URLs.

Performs a breadth-first, same-domain crawl using `requests` + `BeautifulSoup`,
collecting HTML, extracted markdown-ish text, links, JS/CSS asset references,
images, sitemap.xml, robots.txt, and a lightweight technology fingerprint.

This loader deliberately only collects publicly served content (no attempts
to access private/backend resources).
"""
from __future__ import annotations

import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.schemas.metadata import InputType, ProjectMetadata
from app.utils.logger import get_logger

logger = get_logger(__name__)

_TECH_SIGNATURES: dict[str, re.Pattern] = {
    "WordPress": re.compile(r"wp-content|wp-includes", re.I),
    "React": re.compile(r"react(\.min)?\.js|data-reactroot|__NEXT_DATA__", re.I),
    "Next.js": re.compile(r"__NEXT_DATA__|/_next/", re.I),
    "Vue.js": re.compile(r"vue(\.min)?\.js|data-v-", re.I),
    "Angular": re.compile(r"ng-version|angular(\.min)?\.js", re.I),
    "Bootstrap": re.compile(r"bootstrap(\.min)?\.css", re.I),
    "Tailwind CSS": re.compile(r"tailwind", re.I),
    "jQuery": re.compile(r"jquery(\.min)?\.js", re.I),
    "Shopify": re.compile(r"cdn\.shopify\.com", re.I),
    "Cloudflare": re.compile(r"cloudflare", re.I),
    "Google Analytics": re.compile(r"gtag\(|google-analytics\.com|googletagmanager\.com", re.I),
}


class WebsiteCrawlError(Exception):
    """Raised when the initial website URL cannot be reached at all."""


class WebsiteLoader:
    """Crawls a public website and stores its pages, assets, and metadata."""

    def __init__(
        self,
        timeout_seconds: int = 20,
        user_agent: str = "ProjectDataCollectorBot/1.0",
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.5,
    ) -> None:
        self._timeout = timeout_seconds
        self._headers = {"User-Agent": user_agent}
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds

    def collect(
        self,
        url: str,
        project_dir: Path,
        max_pages: int = 50,
        max_depth: int = 2,
    ) -> tuple[dict, dict, list]:
        """
        Crawl `url` (same domain only) and store pages/assets under `project_dir`.
        """
        project_dir.mkdir(parents=True, exist_ok=True)
        pages_dir = project_dir / "pages"
        pages_dir.mkdir(exist_ok=True)

        parsed_root = urlparse(url)
        domain = parsed_root.netloc

        self._download_text(urljoin(url, "/robots.txt"), project_dir / "robots.txt")
        self._download_text(urljoin(url, "/sitemap.xml"), project_dir / "sitemap.xml")

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(url, 0)])

        pages_meta: list[dict] = []
        all_links: set[str] = set()
        js_files: set[str] = set()
        css_files: set[str] = set()
        images: set[str] = set()
        detected_tech: set[str] = set()

        page_index = 0
        while queue and len(visited) < max_pages:
            current_url, depth = queue.popleft()
            if current_url in visited or depth > max_depth:
                continue
            visited.add(current_url)

            html = self._fetch(current_url)
            if html is None:
                continue

            page_index += 1
            soup = BeautifulSoup(html, "html.parser")

            file_stem = f"page_{page_index:03d}"
            (pages_dir / f"{file_stem}.html").write_text(html, encoding="utf-8")
            markdown_text = self._html_to_markdown_like(soup)
            (pages_dir / f"{file_stem}.md").write_text(markdown_text, encoding="utf-8")

            title = soup.title.string.strip() if soup.title and soup.title.string else None
            pages_meta.append(
                {
                    "url": current_url,
                    "title": title,
                    "depth": depth,
                    "file": f"pages/{file_stem}.html",
                }
            )

            for tech, pattern in _TECH_SIGNATURES.items():
                if pattern.search(html):
                    detected_tech.add(tech)

            for script in soup.find_all("script", src=True):
                js_files.add(urljoin(current_url, script["src"]))
            for link_tag in soup.find_all("link", rel=lambda v: v and "stylesheet" in v):
                if link_tag.get("href"):
                    css_files.add(urljoin(current_url, link_tag["href"]))
            for img in soup.find_all("img", src=True):
                images.add(urljoin(current_url, img["src"]))

            for a_tag in soup.find_all("a", href=True):
                absolute = urljoin(current_url, a_tag["href"]).split("#")[0]
                all_links.add(absolute)
                if urlparse(absolute).netloc == domain and absolute not in visited:
                    queue.append((absolute, depth + 1))

        (project_dir / "links.json").write_text(
            self._to_json(sorted(all_links)), encoding="utf-8"
        )
        (project_dir / "assets.json").write_text(
            self._to_json(
                {
                    "javascript": sorted(js_files),
                    "css": sorted(css_files),
                    "images": sorted(images),
                }
            ),
            encoding="utf-8",
        )

        # Build a lightweight tree/files representation for this website capture
        from app.utils.tree_builder import build_tree

        tree, files, _ = build_tree(project_dir, compute_hash=False)

        metadata = ProjectMetadata(
            input_type=InputType.WEBSITE,
            project_name=domain,
            source=url,
            framework=", ".join(sorted(detected_tech)) if detected_tech else None,
            files=[f["path"] for f in files],
            folders=["pages"],
            entry_files=[],
            dependencies=[],
            extra={
                "pages_crawled": len(pages_meta),
                "pages": pages_meta,
                "detected_technologies": sorted(detected_tech),
                "total_links_found": len(all_links),
                "javascript_files": len(js_files),
                "css_files": len(css_files),
                "images": len(images),
            },
        ).model_dump()

        return metadata, tree, files

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> str | None:
        for attempt in range(1, self._max_retries + 1):
            try:
                response = requests.get(url, headers=self._headers, timeout=self._timeout)
                if response.status_code >= 400:
                    logger.warning("Non-OK status %s for %s", response.status_code, url)
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type and attempt == self._max_retries:
                    return None
                return response.text
            except requests.RequestException as exc:
                logger.warning("Attempt %d/%d failed for %s: %s", attempt, self._max_retries, url, exc)
                if attempt == self._max_retries:
                    if url == url:  # first page failing entirely is fatal for the root only
                        return None
                    return None
                time.sleep(self._retry_backoff * attempt)
        return None

    def _download_text(self, url: str, dest: Path) -> None:
        try:
            response = requests.get(url, headers=self._headers, timeout=self._timeout)
            if response.status_code == 200:
                dest.write_text(response.text, encoding="utf-8")
        except requests.RequestException as exc:
            logger.info("Could not download %s: %s", url, exc)

    @staticmethod
    def _html_to_markdown_like(soup: BeautifulSoup) -> str:
        """Very lightweight HTML -> markdown-ish text extraction (headings + paragraphs)."""
        lines: list[str] = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            text = tag.get_text(strip=True)
            if not text:
                continue
            if tag.name in ("h1", "h2", "h3", "h4"):
                prefix = "#" * int(tag.name[1])
                lines.append(f"{prefix} {text}")
            elif tag.name == "li":
                lines.append(f"- {text}")
            else:
                lines.append(text)
        return "\n\n".join(lines)

    @staticmethod
    def _to_json(data) -> str:
        import json

        return json.dumps(data, indent=2, ensure_ascii=False)
