"""HTTP downloads shared by the download scripts: retries and a download log."""

import csv
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import DOWNLOAD_LOG

_session = None


def session() -> requests.Session:
    """A session that retries connection errors and 429/5xx responses with backoff."""
    global _session
    if _session is None:
        retry = Retry(
            total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        _session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=8)
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)  # the gridMET server is http only
    return _session


def get(url: str, ok_missing: bool = False, **kwargs) -> requests.Response | None:
    """GET with retries. Raises on errors; with ok_missing, a 404 or 403 returns None."""
    r = session().get(url, timeout=kwargs.pop("timeout", 180), **kwargs)
    if ok_missing and r.status_code in (403, 404):  # S3 answers 403 or 404 for a missing key
        return None
    r.raise_for_status()
    return r


def log_download(source: str, url: str, note: str = "") -> None:
    """Append one line to data/raw/download_log.csv."""
    DOWNLOAD_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not DOWNLOAD_LOG.exists()
    with DOWNLOAD_LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["downloaded_utc", "source", "url", "note"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), source, url, note])
