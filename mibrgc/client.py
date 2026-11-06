from __future__ import annotations

import time
from pathlib import Path

import requests

from mibrgc.config import REQUEST_DELAY_SECONDS

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class VlrClient:
    """Download public VLR HTML and keep a local copy under data/raw."""

    def __init__(self, raw_dir: Path, delay: float = REQUEST_DELAY_SECONDS, refresh: bool = False):
        self.raw_dir = raw_dir
        self.delay = delay
        self.refresh = refresh
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._last_request = 0.0

    def get(self, url: str, cache_name: str) -> str:
        path = self.raw_dir / cache_name
        if path.exists() and path.stat().st_size > 500 and not self.refresh:
            return path.read_text(encoding="utf-8", errors="replace")

        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0 and self._last_request:
            time.sleep(wait)

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=40)
                self._last_request = time.monotonic()
                if response.status_code == 429 or response.status_code >= 500:
                    time.sleep(2 + attempt * 2)
                    continue
                response.raise_for_status()
                text = response.text
                if "Just a moment" in text and "cf-browser-verification" in text:
                    raise RuntimeError(f"Cloudflare challenge for {url}")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                return text
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(2 + attempt * 2)
        raise RuntimeError(f"Failed to download {url}") from last_error
