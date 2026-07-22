"""
pmd_rainfall_downloader.py

Server-side downloader for PMD (Pakistan Meteorological Department) Daily
Rainfall Reports. This must run outside the browser — PMD blocks
cross-origin / bot-like requests, so a Cloudflare-esque wall makes
fetch()/XHR/axios from client-side JS a dead end. Run this as a scheduled
job (cron, systemd timer, Task Scheduler, GitHub Action, etc.) and have
your frontend read the PDFs (or a JSON summary you generate from them)
from wherever this script saves them.

    python pmd_rainfall_downloader.py
    python pmd_rainfall_downloader.py --days-back 7
    python pmd_rainfall_downloader.py --out ./pdfs --days-back 3
"""

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from pmd_rainfall_parser import sync_pdfs_to_db

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_URL = "https://weather.gov.pk"
LISTING_URL = f"{BASE_URL}/nwfc/daily-rainfall"
FALLBACK_URL_TEMPLATE = f"{BASE_URL}/storage/uploads/nwfc/daily_rainfall/pdf/{{date}}.pdf"

DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pmd_rainfall_pdfs")
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rainfall.db")
REQUEST_TIMEOUT = 20
CHUNK_SIZE = 8192
DEFAULT_DAYS_BACK = 7  # matches the dashboard's 24hr–7day coverage window

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE_URL + "/",
    "Connection": "keep-alive",
}

# --------------------------------------------------------------------------
# Logging — every action (Downloaded / Skipped / Failed) goes to both
# stdout and a log file so a daily cron run leaves an audit trail.
# --------------------------------------------------------------------------

def _build_logger(log_path):
    logger = logging.getLogger("pmd_downloader")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


@dataclass
class RunResult:
    downloaded: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)

    def summary(self):
        return (f"Downloaded: {len(self.downloaded)}, "
                f"Skipped: {len(self.skipped)}, "
                f"Failed: {len(self.failed)}")


class PMDRainfallDownloader:
    def __init__(self, download_dir=DEFAULT_DOWNLOAD_DIR, session=None, logger=None):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

        self.log = logger or _build_logger(
            os.path.join(self.download_dir, "pmd_downloader.log")
        )

    # ----------------------------------------------------------------
    # Step 1 — fetch and parse the listing page for PDF links
    # ----------------------------------------------------------------
    def fetch_listing_html(self):
        try:
            resp = self.session.get(LISTING_URL, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            self.log.warning(f"Could not fetch listing page ({LISTING_URL}): {e}")
            return None

    def find_pdf_links(self, html):
        """Scan the listing page for any <a href="...pdf"> link. Deliberately
        layout-agnostic — no dependence on specific CSS classes, table
        structure, or wording — so small site redesigns don't break it."""
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().endswith(".pdf"):
                links.append(urljoin(BASE_URL, href))

        # de-dupe, preserve order
        seen, unique_links = set(), []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        if unique_links:
            self.log.info(f"Found {len(unique_links)} PDF link(s) on listing page.")
        else:
            self.log.warning("No PDF links found on listing page — will rely on fallback URL pattern.")
        return unique_links

    # ----------------------------------------------------------------
    # Step 2 — date extraction from a URL, and fallback URL construction
    # ----------------------------------------------------------------
    @staticmethod
    def extract_date_from_url(url):
        """Best-effort extraction of a report date from a PDF filename.
        Handles DD-MM-YYYY, DD_MM_YYYY, and YYYY-MM-DD style names."""
        filename = os.path.basename(urlparse(url).path)
        patterns = [
            (r"(\d{2})[-_](\d{2})[-_](\d{4})", "dmy"),   # DD-MM-YYYY
            (r"(\d{4})[-_](\d{2})[-_](\d{2})", "ymd"),   # YYYY-MM-DD
        ]
        for pattern, order in patterns:
            m = re.search(pattern, filename)
            if not m:
                continue
            a, b, c = m.groups()
            try:
                if order == "ymd":
                    return datetime(int(a), int(b), int(c)).date()
                else:
                    return datetime(int(c), int(b), int(a)).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def fallback_url_for_date(date_obj):
        return FALLBACK_URL_TEMPLATE.format(date=date_obj.strftime("%d-%m-%Y"))

    # ----------------------------------------------------------------
    # Step 3 — verify before committing to a download
    # ----------------------------------------------------------------
    def verify_pdf_url(self, url):
        """Confirm the URL resolves to HTTP 200 and Content-Type: application/pdf
        before spending bandwidth on a full download. Falls back to a small
        ranged GET if the server doesn't support HEAD properly (common on
        some PHP/Apache setups)."""
        try:
            resp = self.session.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)

            if resp.status_code == 404:
                return False

            if resp.status_code >= 400 or "content-type" not in resp.headers:
                resp = self.session.get(
                    url, timeout=REQUEST_TIMEOUT, stream=True,
                    headers={"Range": "bytes=0-1023"},
                )
                if resp.status_code == 404:
                    return False
                if resp.status_code not in (200, 206):
                    self.log.warning(f"Unexpected status {resp.status_code} verifying {url}")
                    return False

            content_type = resp.headers.get("Content-Type", "").lower()
            if "application/pdf" not in content_type:
                self.log.warning(f"Not a PDF (Content-Type: {content_type or 'unknown'}): {url}")
                return False

            return True

        except requests.RequestException as e:
            self.log.warning(f"Verification request failed for {url}: {e}")
            return False

    # ----------------------------------------------------------------
    # Step 4 — streamed download, skip-if-exists, atomic write
    # ----------------------------------------------------------------
    def download_pdf(self, url, date_obj=None):
        """Returns (filepath_or_None, status) where status is one of
        'downloaded', 'skipped', 'failed'."""
        date_obj = date_obj or self.extract_date_from_url(url) or datetime.now().date()
        filename = f"{date_obj.strftime('%Y-%m-%d')}.pdf"
        filepath = os.path.join(self.download_dir, filename)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            self.log.info(f"Skipped (already exists): {filename}")
            return filepath, "skipped"

        tmp_path = filepath + ".part"
        try:
            with self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True) as resp:
                resp.raise_for_status()

                content_type = resp.headers.get("Content-Type", "").lower()
                if "application/pdf" not in content_type:
                    self.log.error(f"Refusing to save non-PDF content ({content_type}) from {url}")
                    return None, "failed"

                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)

            os.replace(tmp_path, filepath)
            self.log.info(f"Downloaded: {filename}  <-  {url}")
            return filepath, "downloaded"

        except requests.RequestException as e:
            self.log.error(f"Failed to download {url}: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return None, "failed"

    # ----------------------------------------------------------------
    # Orchestration
    # ----------------------------------------------------------------
    def run(self, days_back=DEFAULT_DAYS_BACK):
        """
        1. Try the listing page first; download+verify anything it links to.
        2. For any date in the requested window (today back `days_back` days)
           not already covered by a discovered link, probe the fallback
           date-pattern URL, verify it, and download if valid.
        3. Never assume the listing page parsed cleanly — if it returned
           nothing (site down, layout changed beyond recognition, blocked),
           fall through entirely to the date-pattern probe for the whole
           window.
        """
        result = RunResult()

        html = self.fetch_listing_html()
        discovered_links = self.find_pdf_links(html) if html else []

        covered_dates = set()
        for url in discovered_links:
            date_obj = self.extract_date_from_url(url)
            if date_obj:
                covered_dates.add(date_obj)

            if not self.verify_pdf_url(url):
                self.log.warning(f"Skipping unverified listing link: {url}")
                result.failed.append(url)
                continue

            path, status = self.download_pdf(url, date_obj)
            self._record(result, path, url, status)

        today = datetime.now().date()
        for offset in range(days_back):
            date_obj = today - timedelta(days=offset)
            if date_obj in covered_dates:
                continue

            fallback_url = self.fallback_url_for_date(date_obj)
            self.log.info(f"No listing link for {date_obj}, probing fallback: {fallback_url}")

            if not self.verify_pdf_url(fallback_url):
                self.log.info(f"No valid report found for {date_obj}.")
                continue

            path, status = self.download_pdf(fallback_url, date_obj)
            self._record(result, path, fallback_url, status)

        self.log.info(f"Run complete. {result.summary()}")
        return result

    @staticmethod
    def _record(result, path, url, status):
        if status == "downloaded" and path:
            result.downloaded.append(path)
        elif status == "skipped" and path:
            result.skipped.append(path)
        else:
            result.failed.append(url)


def main():
    parser = argparse.ArgumentParser(description="Download PMD Daily Rainfall Report PDFs.")
    parser.add_argument("--out", default=DEFAULT_DOWNLOAD_DIR, help="Directory to save PDFs into.")
    parser.add_argument("--days-back", type=int, default=DEFAULT_DAYS_BACK,
                         help="How many days back to probe via the fallback URL pattern (default: 7).")
    parser.add_argument("--db", default=DEFAULT_DB_PATH,
                         help="Path to the SQLite database that stores parsed rainfall readings.")
    parser.add_argument("--skip-db", action="store_true",
                         help="Download PDFs only — don't parse them into the database.")
    parser.add_argument("--rebuild-db", action="store_true",
                         help="Reparse every PDF in --out, even dates already present in the database.")
    args = parser.parse_args()

    downloader = PMDRainfallDownloader(download_dir=args.out)
    result = downloader.run(days_back=args.days_back)

    print(f"\n{result.summary()}")
    if result.downloaded:
        print("Downloaded files:")
        for f in result.downloaded:
            print(f"  - {f}")

    if not args.skip_db:
        updated_dates = sync_pdfs_to_db(
            pdf_dir=args.out, db_path=args.db,
            logger=downloader.log, force=args.rebuild_db,
        )
        print(f"\nDatabase sync: {len(updated_dates)} date(s) (re)parsed into {args.db}")
        if updated_dates:
            print("Updated dates:")
            for d in updated_dates:
                print(f"  - {d}")


if __name__ == "__main__":
    main()