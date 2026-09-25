"""Task 2 - Crawl public articles into landing/news JSON files."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://www.baovietnhantho.com.vn/san-pham/dau-tu/an-khang-hanh-phuc",
]

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

CONTENT_START_MARKERS = (
    "# B\u1ea3o hi\u1ec3m li\u00ean k\u1ebft chung An Khang H\u1ea1nh Ph\u00fac 2024",
    "## B\u1ea3o hi\u1ec3m li\u00ean k\u1ebft chung An Khang H\u1ea1nh Ph\u00fac 2024",
    "## S\u1ea3n ph\u1ea9m ng\u1eebng tri\u1ec3n khai",
)
CONTENT_END_MARKERS = (
    "## N\u1ebfu b\u1ea1n ph\u00e2n v\u00e2n gi\u1eefa c\u00e1c s\u1ea3n ph\u1ea9m b\u1ea3o hi\u1ec3m",
    "## S\u1ea3n ph\u1ea9m c\u00f3 th\u1ec3 b\u1ea1n quan t\u00e2m",
    "Li\u00ean h\u1ec7 v\u1edbi ch\u00fang t\u00f4i",
)


def clean_article_markdown(markdown: str) -> str:
    """Keep the article body and remove repeated site chrome."""
    text = markdown.replace("\r\n", "\n").strip()

    starts = [
        position
        for marker in CONTENT_START_MARKERS
        if (position := text.find(marker)) >= 0
    ]
    if starts:
        text = text[min(starts):]
        if not text.startswith("# B\u1ea3o hi\u1ec3m li\u00ean k\u1ebft chung"):
            text = "# B\u1ea3o hi\u1ec3m li\u00ean k\u1ebft chung An Khang H\u1ea1nh Ph\u00fac 2024\n\n" + text

    ends = [
        position
        for marker in CONTENT_END_MARKERS
        if (position := text.find(marker)) > 0
    ]
    if ends:
        text = text[:min(ends)]

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_text(result: object) -> str:
    value = getattr(result, "markdown", "")
    if hasattr(value, "raw_markdown"):
        value = value.raw_markdown
    return str(value or "").strip()


async def crawl_article(url: str) -> dict[str, str]:
    browser_config = BrowserConfig(
        headless=True,
        user_agent=BROWSER_USER_AGENT,
        enable_stealth=True,
        verbose=False,
    )
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=True,
        excluded_tags=[
            "nav",
            "footer",
            "form",
            "script",
            "style",
            "noscript",
        ],
        remove_forms=True,
        remove_overlay_elements=True,
        remove_consent_popups=True,
        wait_until="domcontentloaded",
        page_timeout=60000,
        delay_before_return_html=1.0,
        verbose=False,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    if not result.success:
        detail = result.error_message or f"HTTP {result.status_code}"
        raise RuntimeError(f"Crawl failed for {url}: {detail}")

    content = clean_article_markdown(markdown_text(result))
    if len(content) < 200:
        raise ValueError(f"Crawled content is too short for {url}")

    metadata = result.metadata or {}
    title = str(metadata.get("title") or "Unknown").strip()
    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": content,
    }


async def crawl_all() -> list[Path]:
    """Crawl configured URLs and save deterministic JSON outputs."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    failures: list[str] = []

    for index, url in enumerate(ARTICLE_URLS, start=1):
        try:
            article = await crawl_article(url)
            output = DATA_DIR / f"article_{index:02d}.json"
            output.write_text(
                json.dumps(article, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            outputs.append(output)
            print(f"Saved: {output}")
        except Exception as error:
            failures.append(f"{url}: {error}")
        if index < len(ARTICLE_URLS):
            await asyncio.sleep(2)

    if failures:
        raise RuntimeError("\n".join(failures))
    return outputs


if __name__ == "__main__":
    asyncio.run(crawl_all())
