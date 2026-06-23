import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, quote_plus, urlparse

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


class BaseComicProvider(ABC):
    """Abstract base for comic site providers.

    Subclasses must set ``name`` and ``base_url``.  The default implementations
    of every scraping method work for sites that share the readcomiconline.li
    HTML structure (which rcostation.xyz does).  Override any method for sites
    with a different layout.
    """

    name: str = ""
    base_url: str = ""

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._http = httpx.Client(timeout=30, follow_redirects=True)

    # ---------- Context manager ----------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ---------- Lazy browser ----------

    @property
    def browser(self):
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self._headless)
        return self._browser

    def _new_page(self):
        return self.browser.new_page()

    # ---------- Search ----------

    def search(self, query: str) -> list[dict]:
        """Search for comics by keyword.

        Returns a list of dicts: ``[{"title": str, "url": str, "thumbnail": str}, ...]``
        """
        url = f"{self.base_url}/Search/Comic?keyword={quote_plus(query)}"
        page = self._new_page()
        try:
            page.goto(url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass

            try:
                page.wait_for_selector("a[href*='/Comic/']", timeout=10000)
            except PlaywrightTimeout:
                return []

            items = page.eval_on_selector_all(
                "a[href*='/Comic/']",
                """els => els.map(e => {
                    const img = e.querySelector('img');
                    return {
                        href: (new URL(e.getAttribute('href') || e.href, document.baseURI)).pathname,
                        text: (e.textContent || '').trim(),
                        thumb: img ? img.src : ''
                    };
                })""",
            )

            results = []
            seen = set()
            for item in items:
                href = item.get("href", "")
                if not href:
                    continue

                raw_path = href.split("?")[0]
                parts = raw_path.strip("/").split("/")
                if len(parts) != 2 or parts[0].lower() != "comic":
                    continue

                link = urljoin(self.base_url, raw_path)
                if link in seen:
                    continue
                seen.add(link)

                title = " ".join(item.get("text", "").split())
                if not title:
                    slug = urlparse(link).path.rstrip("/").split("/")[-1]
                    title = slug.replace("-", " ").replace("_", " ")
                    title = " ".join(title.split())

                thumb = item.get("thumb", "")
                if thumb and not thumb.startswith("http"):
                    thumb = urljoin(self.base_url, thumb)

                results.append({"title": title, "url": link, "thumbnail": thumb})

            return results
        finally:
            page.close()

    # ---------- Comic info ----------

    def get_comic_info(self, comic_url: str) -> dict:
        """Fetch metadata for a comic.

        Returns a dict with keys: cover, summary, genres, status, year, publisher.
        """
        page = self._new_page()
        try:
            page.goto(comic_url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass

            info = page.evaluate("""() => {
                const result = {cover: '', summary: '', genres: '', status: '', year: '', publisher: ''};

                const imgs = document.querySelectorAll('img');
                for (const img of imgs) {
                    if (img.src && img.src.includes('/Uploads/') && img.naturalWidth > 50) {
                        result.cover = img.src;
                        break;
                    }
                }

                const bc = document.querySelector('.barContent');
                if (bc) {
                    const paragraphs = bc.querySelectorAll('p');
                    for (const p of paragraphs) {
                        const label = p.querySelector('span.info');
                        if (!label) continue;
                        const key = (label.textContent || '').trim().toLowerCase().replace(':', '');

                        if (key === 'genres' || key === 'genre') {
                            const links = p.querySelectorAll('a');
                            const genres = [];
                            for (const a of links) {
                                const t = (a.textContent || '').trim();
                                if (t && t !== '.') genres.push(t);
                            }
                            result.genres = genres.join(', ');
                        } else {
                            let val = p.textContent || '';
                            val = val.replace(label.textContent || '', '').trim();
                            val = val.replace(/^[:\\s]+/, '').trim();
                            val = val.split('\\n')[0].replace(/\\u00a0/g, ' ').trim();

                            if (key === 'status')           result.status = val;
                            if (key === 'year of release')  result.year = val;
                            if (key === 'publisher')        result.publisher = val;
                        }
                    }

                    for (const p of paragraphs) {
                        if (p.querySelector('span.info')) continue;
                        const text = (p.textContent || '').trim();
                        if (text.length > 40) {
                            result.summary = text;
                            break;
                        }
                    }
                }

                return result;
            }""")

            return info if isinstance(info, dict) else {
                "cover": "", "summary": "", "genres": "", "status": "", "year": "", "publisher": ""
            }
        finally:
            page.close()

    # ---------- Issues ----------

    def get_issues(self, comic_url: str) -> list[dict]:
        """Get the list of issues for a comic.

        Returns a list of dicts: ``[{"title": str, "url": str}, ...]``
        """
        page = self._new_page()
        try:
            page.goto(comic_url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass
            page.wait_for_selector("a[href]", timeout=10000)

            items = page.eval_on_selector_all(
                "a[href]",
                """els => els.map(e => ({
                    href: (new URL(e.getAttribute('href') || e.href, document.baseURI)).pathname,
                    text: (e.textContent || '').trim()
                }))""",
            )

            parsed_comic = urlparse(comic_url)
            comic_path = parsed_comic.path.rstrip("/")
            comic_slug = None
            if "/Comic/" in comic_path:
                try:
                    comic_slug = comic_path.split("/Comic/")[1]
                except Exception:
                    pass

            issues = []
            seen = set()
            for item in items:
                href = item.get("href", "")
                if not href:
                    continue

                raw_path = href.split("?")[0]
                link = urljoin(self.base_url, raw_path)
                path = urlparse(link).path.rstrip("/")

                is_issue_link = "/Issue-" in path
                is_under_comic = comic_slug and path.startswith(f"/Comic/{comic_slug}/") and path != comic_path
                if not (is_issue_link or is_under_comic):
                    continue

                if link in seen:
                    continue
                seen.add(link)

                title = " ".join(item.get("text", "").split())
                if not title:
                    slug = path.split("/")[-1]
                    title = slug.replace("-", " ").replace("_", " ")
                    title = " ".join(title.split())

                issues.append({"title": title, "url": link})

            return issues
        finally:
            page.close()

    # ---------- Page images ----------

    def get_issue_image_urls(self, issue_url: str) -> list[str]:
        """Navigate to the issue in all-pages mode and collect image URLs.

        Returns a list of image URL strings, one per comic page.
        """
        separator = "&" if "?" in issue_url else "?"
        all_pages_url = f"{issue_url}{separator}readType=1"

        page = self._new_page()
        try:
            page.goto(all_pages_url, timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            try:
                page.wait_for_selector("div#divImage img", timeout=15000)
            except PlaywrightTimeout:
                return []

            page.evaluate("""async () => {
                const imgs = document.querySelectorAll('div#divImage img');

                for (const img of imgs) {
                    img.scrollIntoView({behavior: 'instant'});
                    await new Promise(r => setTimeout(r, 250));
                }

                for (const img of imgs) {
                    if (img.src.includes('blank.gif') || !img.src) {
                        img.scrollIntoView({behavior: 'instant'});
                        await new Promise(r => setTimeout(r, 300));
                    }
                }

                const deadline = Date.now() + 15000;
                while (Date.now() < deadline) {
                    const blanks = [...imgs].filter(
                        i => i.style.display !== 'none' && (i.src.includes('blank.gif') || !i.src)
                    );
                    if (blanks.length === 0) break;
                    blanks[0].scrollIntoView({behavior: 'instant'});
                    await new Promise(r => setTimeout(r, 500));
                }
            }""")

            image_urls = page.evaluate("""() => {
                const imgs = document.querySelectorAll('div#divImage img');
                const urls = [];
                for (const img of imgs) {
                    const src = img.src || '';
                    if (img.style.display === 'none') continue;
                    if (!src || src.includes('blank.gif')) continue;
                    urls.push(src);
                }
                return urls;
            }""")

            return image_urls if isinstance(image_urls, list) else []
        finally:
            page.close()

    # ---------- Download ----------

    def _download_single_page(self, img_url: str, filepath: str) -> bool:
        """Download a single image to disk. Returns True on success."""
        if os.path.exists(filepath):
            return True
        try:
            response = self._http.get(img_url)
            response.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(response.content)
            return True
        except Exception:
            return False

    def download_issue(self, issue: dict, output_dir: str = "downloads",
                       on_page_done=None, max_workers: int = 6) -> str:
        """Download all pages of a single issue.

        Returns the path to the downloaded issue directory.
        """
        issue_url = issue["url"]
        parsed = urlparse(issue_url)
        path_parts = parsed.path.rstrip("/").split("/")

        comic_title = path_parts[2] if len(path_parts) > 2 else "Unknown"
        comic_title = comic_title.replace("-", " ").replace("_", " ")
        comic_title = " ".join(comic_title.split())

        issue_title = issue["title"].replace("/", "_").replace("\\", "_")

        issue_dir = os.path.join(output_dir, comic_title, issue_title)
        os.makedirs(issue_dir, exist_ok=True)

        image_urls = self.get_issue_image_urls(issue_url)
        total = len(image_urls)

        if total == 0:
            return issue_dir

        tasks = []
        for page_num, img_url in enumerate(image_urls, start=1):
            if not img_url:
                continue
            ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
            filename = f"{page_num:03d}{ext}"
            filepath = os.path.join(issue_dir, filename)
            tasks.append((page_num, img_url, filepath))

        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_page = {
                pool.submit(self._download_single_page, img_url, filepath): page_num
                for page_num, img_url, filepath in tasks
            }
            for future in as_completed(future_to_page):
                completed += 1
                if on_page_done:
                    on_page_done(completed, total)

        return issue_dir

    # ---------- Cleanup ----------

    def close(self):
        """Release all resources."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        if self._http:
            try:
                self._http.close()
            except Exception:
                pass
