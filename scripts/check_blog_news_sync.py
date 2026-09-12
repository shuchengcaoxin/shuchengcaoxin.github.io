"""Check that every listed blog post is linked consistently across the site.

The script uses only the Python standard library. Run it from any directory:

    python scripts/check_blog_news_sync.py
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


SITE_ORIGIN = "https://shuchengcaoxin.github.io"
SITE_HOST = "shuchengcaoxin.github.io"
BLOG_ARTICLE_PATTERN = re.compile(r"^/blog/([^/]+)/$")


class LinkCollector(HTMLParser):
    """Collect href values from every anchor in an HTML document."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


class NewsSectionLinkCollector(HTMLParser):
    """Collect anchor href values only from ``<section id="news">``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found_news_section = False
        self.links: list[str] = []
        self._section_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        attr_map = dict(attrs)

        if self._section_depth:
            if tag == "section":
                self._section_depth += 1
            if tag == "a" and attr_map.get("href"):
                self.links.append(attr_map["href"])
            return

        if tag == "section" and attr_map.get("id") == "news":
            self.found_news_section = True
            self._section_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self._section_depth and tag.lower() == "section":
            self._section_depth -= 1


def parse_html(path: Path, parser: HTMLParser) -> None:
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()


def normalize_internal_blog_url(href: str) -> str | None:
    """Return a canonical ``/blog/<slug>/`` path for an internal URL."""

    parsed = urlsplit(href.strip())
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return None
    if parsed.netloc and parsed.netloc.lower() != SITE_HOST:
        return None

    path = unquote(parsed.path)
    match = BLOG_ARTICLE_PATTERN.fullmatch(path)
    if not match or match.group(1) in {".", ".."}:
        return None
    return path


def unique_in_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def collect_sitemap_urls(path: Path) -> set[str]:
    root = ElementTree.parse(path).getroot()
    return {
        (element.text or "").strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "loc" and element.text
    }


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"[FAIL] {message}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    blog_index = repo_root / "blog" / "index.html"
    home_index = repo_root / "index.html"
    sitemap = repo_root / "sitemap.xml"
    failures: list[str] = []

    print(f"Repository: {repo_root}")

    missing_inputs = [
        path for path in (blog_index, home_index, sitemap) if not path.is_file()
    ]
    if missing_inputs:
        for path in missing_inputs:
            fail(f"Required file is missing: {path.relative_to(repo_root)}", failures)
        print(f"\nResult: FAILED ({len(failures)} issue(s))")
        return 1

    try:
        blog_parser = LinkCollector()
        parse_html(blog_index, blog_parser)
        blog_urls = unique_in_order(
            [
                normalized
                for href in blog_parser.links
                if (normalized := normalize_internal_blog_url(href)) is not None
            ]
        )

        news_parser = NewsSectionLinkCollector()
        parse_html(home_index, news_parser)
        news_urls = {
            normalized
            for href in news_parser.links
            if (normalized := normalize_internal_blog_url(href)) is not None
        }

        sitemap_urls = collect_sitemap_urls(sitemap)
    except (OSError, UnicodeError, ElementTree.ParseError) as exc:
        fail(f"Could not parse a site file: {exc}", failures)
        print(f"\nResult: FAILED ({len(failures)} issue(s))")
        return 1

    if not blog_urls:
        fail("No internal /blog/<slug>/ article links found in blog/index.html", failures)
        print(f"\nResult: FAILED ({len(failures)} issue(s))")
        return 1

    print(f"Found {len(blog_urls)} blog article(s).")

    if news_parser.found_news_section:
        print('[PASS] index.html contains <section id="news">')
    else:
        fail('index.html does not contain <section id="news">', failures)

    for blog_url in blog_urls:
        slug = BLOG_ARTICLE_PATTERN.fullmatch(blog_url).group(1)  # type: ignore[union-attr]
        article_path = repo_root / "blog" / slug / "index.html"
        canonical_url = f"{SITE_ORIGIN}{blog_url}"

        print(f"\nArticle: {blog_url}")

        if article_path.is_file():
            print(f"[PASS] Article file exists: {article_path.relative_to(repo_root)}")
        else:
            fail(
                f"{blog_url} is missing its article file: "
                f"{article_path.relative_to(repo_root)}",
                failures,
            )

        if blog_url in news_urls:
            print("[PASS] Homepage News section contains the article link")
        else:
            fail(f"{blog_url} is missing from the News section in index.html", failures)

        if canonical_url in sitemap_urls:
            print(f"[PASS] sitemap.xml contains: {canonical_url}")
        else:
            fail(f"sitemap.xml is missing: {canonical_url}", failures)

    if failures:
        print(f"\nResult: FAILED ({len(failures)} issue(s))")
        return 1

    print("\nResult: PASSED. Blog, News, and sitemap are synchronized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
