import os
import re
import requests
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus, urlparse
from playwright.sync_api import sync_playwright


class ComicScraper:
    def __init__(self, base_url="https://readcomiconline.li"):
        self.base_url = base_url
        self.scraper = cloudscraper.create_scraper()
        self.browser = None
        self.playwright = None

    # ---------- Core helpers ----------

    def _get_soup(self, url):
        r = self.scraper.get(url, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    def _init_playwright(self):
        if self.browser is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
        return self.browser

    def search(self, query):
        url = f"{self.base_url}/Search/Comic?keyword={quote_plus(query)}"
        browser = self._init_playwright()
        page = browser.new_page()
        try:
            page.goto(url, timeout=60000)
            # Wait for network to settle but don't fail if it doesn't fully idle.
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass
            # Ensure at least one comic link appears
            page.wait_for_selector("a[href*='/Comic/']", timeout=10000)

            items = page.eval_on_selector_all(
                "a[href*='/Comic/']",
                "els => els.map(e => ({href: (new URL(e.getAttribute('href')||e.href, document.baseURI)).pathname, raw: (new URL(e.getAttribute('href')||e.href, document.baseURI)).href, text: (e.textContent||'').trim()}))"
            )

            results = []
            seen = set()
            for it in items:
                href = (it.get("href") if isinstance(it, dict) else None) or ""
                if not href:
                    continue

                raw_path = href.split("?")[0]
                # Only accept top-level /Comic/<slug> links (avoid issue or nested links)
                parts = raw_path.strip("/").split("/")
                if len(parts) != 2 or parts[0].lower() != "comic":
                    continue

                link = urljoin(self.base_url, raw_path)
                title = (it.get("text") if isinstance(it, dict) else None) or ""
                # Normalize whitespace
                title = " ".join(title.split())
                if not title:
                    # fallback to slug
                    seg = urlparse(link).path.rstrip("/").split("/")[-1]
                    title = seg.replace("-", " ").replace("_", " ")
                    title = " ".join(title.split())

                if link in seen:
                    continue
                seen.add(link)
                results.append({"title": title, "url": link})

            return results
        finally:
            try:
                page.close()
            except Exception:
                pass

    def get_issues(self, comic_url):
        browser = self._init_playwright()
        page = browser.new_page()
        try:
            page.goto(comic_url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass
            page.wait_for_selector("a[href]", timeout=10000)

            items = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({href: (new URL(e.getAttribute('href')||e.href, document.baseURI)).pathname, raw: (new URL(e.getAttribute('href')||e.href, document.baseURI)).href, text: (e.textContent||'').trim()}))"
            )

            parsed_comic = urlparse(comic_url)
            comic_path = parsed_comic.path.rstrip("/")
            comic_slug = None
            if "/Comic/" in comic_path:
                try:
                    comic_slug = comic_path.split("/Comic/")[1]
                except Exception:
                    comic_slug = None

            issues = []
            seen = set()
            for it in items:
                href = (it.get("href") if isinstance(it, dict) else None) or ""
                if not href:
                    continue
                raw = href.split("?")[0]
                link = urljoin(self.base_url, raw)

                parsed = urlparse(link)
                path = parsed.path.rstrip("/")

                # include explicit Issue- links or links under the same comic slug
                if "/Issue-" not in path and not (comic_slug and path.startswith(f"/Comic/{comic_slug}/")):
                    continue

                if link in seen:
                    continue

                title = (it.get("text") if isinstance(it, dict) else None) or ""
                title = " ".join(title.split())
                if not title:
                    seg = path.split("/")[-1]
                    title = seg.replace("-", " ").replace("_", " ") or link
                    title = " ".join(title.split())

                seen.add(link)
                issues.append({"title": title, "url": link})

            return issues
        finally:
            try:
                page.close()
            except Exception:
                pass

    # ---------- Issue scraping ----------

    def get_num_pages(self, issue_url):
        browser = self._init_playwright()
        page = browser.new_page()
        try:
            page.goto(issue_url, timeout=60000)
            page.wait_for_selector("select#selectPage", timeout=10000)

            # fetch both value and text for each option
            opts = page.eval_on_selector_all(
                "select#selectPage option",
                "els => els.map(e => ({v: (e.value||'').trim(), t: (e.textContent||'').trim()}))"
            )

            max_num = None
            for opt in opts:
                # opt is expected to be a dict like {'v': '...', 't': '...'}
                t_raw = opt.get("t") if isinstance(opt, dict) else ""
                v_raw = opt.get("v") if isinstance(opt, dict) else ""

                # Prefer numbers from the visible text (human-facing). If none, use the value.
                nums_text = re.findall(r"(\d+)", t_raw) if t_raw else []
                nums_value = re.findall(r"(\d+)", v_raw) if v_raw else []
                nums = nums_text if nums_text else nums_value

                if not nums:
                    continue

                try:
                    candidates = [int(n) for n in nums]
                except ValueError:
                    continue

                opt_max = max(candidates)
                if max_num is None or opt_max > max_num:
                    max_num = opt_max

            return max_num if max_num is not None else 1
        except Exception:
            return 1
        finally:
            try:
                page.close()
            except Exception:
                pass

    def get_pages_links(self, issue_url):
        num_pages = self.get_num_pages(issue_url)
        links_of_pages = []

        for page_num in range(1, num_pages + 1):
            url = f"{issue_url}#{page_num}"
            links_of_pages.append(url)

        return links_of_pages

    def get_issue_images(self, issue_url):
        """
        Uses Playwright because images are injected dynamically.
        """
        browser = self._init_playwright()
        page = browser.new_page()
        page.goto(issue_url, timeout=60000)

        page.wait_for_selector("img")
        images = page.eval_on_selector_all(
            "img",
            "els => els.map(e => e.src).filter(src => src.includes('jpg') || src.includes('png'))"
        )

        page.close()
        return images

    # ---------- Download ----------

    def download_issue(self, issue, base_dir="downloads"):
        issue_dir = os.path.join(
            base_dir,
            issue["title"].replace("/", "_")
        )
        os.makedirs(issue_dir, exist_ok=True)

        images = self.get_issue_images(issue["url"])

        for i, img_url in enumerate(images, start=1):
            ext = os.path.splitext(img_url)[1].split("?")[0]
            filename = f"{i:03d}{ext}"
            path = os.path.join(issue_dir, filename)

            if os.path.exists(path):
                continue

            r = requests.get(img_url, stream=True, timeout=30)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

    # ---------- Cleanup ----------

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.browser = None
        self.playwright = None
