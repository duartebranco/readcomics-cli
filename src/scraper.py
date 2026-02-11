import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, quote_plus, urlparse

import httpx


class ComicScraper:
    """Scrapes readcomiconline.li for comic search, issue listing, and page downloading."""

    def __init__(self, base_url="https://readcomiconline.li", headless=True):
        self.base_url = base_url
        # headless parameter kept for API compatibility but not used
        self._headless = headless
        # Use realistic browser headers to avoid Cloudflare blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
        self._http = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers=headers
        )

    # ---------- Context manager ----------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ---------- Search ----------

    def search(self, query):
        """
        Search for comics by keyword using POST request.

        Returns a list of dicts: [{"title": str, "url": str, "thumbnail": str}, ...]
        """
        url = f"{self.base_url}/Search/Comic"
        
        try:
            # Use POST request as per NOBORU pattern
            response = self._http.post(url, data={"keyword": query})
            response.raise_for_status()
            html = response.text
        except Exception:
            return []

        # Parse HTML for comic links and thumbnails
        # Pattern matches: <a href="/Comic/slug"><img src="..."></a> or <a href="/Comic/slug">Title</a>
        # Group 1: Comic path (e.g., "/Comic/Batman")
        # Group 2: Thumbnail URL (optional)
        # Group 3: Link text/title
        pattern = r'<a[^>]*href="(/Comic/[^/"]+)[^"]*"[^>]*>(?:[^<]*<img[^>]*src="([^"]*)"[^>]*>)?[^<]*([^<]*)</a>'
        
        results = []
        seen = set()
        matches = re.finditer(pattern, html, re.IGNORECASE)
        
        for match in matches:
            href = match.group(1)
            thumb = match.group(2) or ""
            text = match.group(3) or ""
            
            # Clean up the path
            raw_path = href.split("?")[0]
            parts = raw_path.strip("/").split("/")
            
            # Only accept top-level /Comic/<slug> links (not issue links)
            if len(parts) != 2 or parts[0].lower() != "comic":
                continue
            
            link = urljoin(self.base_url, raw_path)
            if link in seen:
                continue
            seen.add(link)
            
            # Extract title from the surrounding text or URL
            title = re.sub(r'<[^>]+>', '', text).strip()
            title = " ".join(title.split())
            
            if not title:
                slug = urlparse(link).path.rstrip("/").split("/")[-1]
                title = slug.replace("-", " ").replace("_", " ")
                title = " ".join(title.split())
            
            # Make thumbnail absolute URL if needed
            if thumb and not thumb.startswith("http"):
                thumb = urljoin(self.base_url, thumb)
            
            results.append({"title": title, "url": link, "thumbnail": thumb})
        
        return results

    # ---------- Comic info ----------

    def get_comic_info(self, comic_url):
        """
        Fetch metadata for a comic: cover image URL, summary, genres, status, etc.

        Returns a dict with keys: cover, summary, genres, status, year, publisher.
        All values are strings (empty string if not found).
        """
        try:
            response = self._http.get(comic_url)
            response.raise_for_status()
            html = response.text
        except Exception:
            return {
                "cover": "", "summary": "", "genres": "", 
                "status": "", "year": "", "publisher": ""
            }
        
        info = {
            "cover": "", "summary": "", "genres": "", 
            "status": "", "year": "", "publisher": ""
        }
        
        # Extract cover image (look for /Uploads/ images)
        cover_match = re.search(r'<img[^>]*src="([^"]*\/Uploads\/[^"]*)"[^>]*>', html, re.IGNORECASE)
        if cover_match:
            cover_url = cover_match.group(1)
            if not cover_url.startswith("http"):
                cover_url = urljoin(self.base_url, cover_url)
            info["cover"] = cover_url
        
        # Extract info from the barContent section
        # Look for <p><span class="info">Label:</span>&nbsp;Value</p> patterns
        
        # Genres: <span class="info">Genres:</span>&nbsp;<a>Genre1</a>, <a>Genre2</a>
        genres_match = re.search(
            r'<span class="info">Genres?:</span>&nbsp;(.*?)</p>',
            html, re.IGNORECASE | re.DOTALL
        )
        if genres_match:
            genres_html = genres_match.group(1)
            # Extract all <a> tag contents
            genre_links = re.findall(r'<a[^>]*>([^<]+)</a>', genres_html)
            # Filter out periods (used as separators in the HTML)
            info["genres"] = ", ".join(g.strip() for g in genre_links if g.strip() and g.strip() != ".")
        
        # Status: <span class="info">Status:</span>&nbsp;Completed
        status_match = re.search(
            r'<span class="info">Status:</span>&nbsp;([^<\n]+)',
            html, re.IGNORECASE
        )
        if status_match:
            info["status"] = status_match.group(1).strip()
        
        # Year: <span class="info">Year of Release:</span>&nbsp;2020
        year_match = re.search(
            r'<span class="info">Year of Release:</span>&nbsp;([^<\n]+)',
            html, re.IGNORECASE
        )
        if year_match:
            info["year"] = year_match.group(1).strip()
        
        # Publisher: <span class="info">Publisher:</span>&nbsp;DC Comics
        publisher_match = re.search(
            r'<span class="info">Publisher:</span>&nbsp;([^<\n]+)',
            html, re.IGNORECASE
        )
        if publisher_match:
            info["publisher"] = publisher_match.group(1).strip()
        
        # Summary: Look for <p> tags with substantial text but no span.info inside
        # Usually appears after the info spans
        summary_pattern = r'<p>(?!<span class="info">)([^<]{40,}?)</p>'
        summary_match = re.search(summary_pattern, html, re.IGNORECASE)
        if summary_match:
            summary = summary_match.group(1).strip()
            # Clean up HTML entities
            summary = re.sub(r'&nbsp;', ' ', summary)
            summary = re.sub(r'\s+', ' ', summary)
            info["summary"] = summary
        
        return info

    # ---------- Issues ----------

    def get_issues(self, comic_url):
        """
        Get the list of issues for a comic.

        Returns a list of dicts: [{"title": str, "url": str}, ...]
        Issues are returned in the order they appear on the page.
        """
        try:
            response = self._http.get(comic_url)
            response.raise_for_status()
            html = response.text
        except Exception:
            return []
        
        # Extract comic slug from URL
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
        
        # Pattern based on NOBORU: <td>[^<]*<a[^>]*href="/Comic/[^/]*/([^"]*)"[^>]*>\s*(.*?)</a>
        # This finds issue links under the comic
        pattern = r'<a[^>]*href="(/Comic/[^/]+/[^"]+)"[^>]*>([^<]*)</a>'
        matches = re.finditer(pattern, html, re.IGNORECASE)
        
        for match in matches:
            href = match.group(1)
            text = match.group(2)
            
            # Clean up the path
            raw_path = href.split("?")[0]
            link = urljoin(self.base_url, raw_path)
            path = urlparse(link).path.rstrip("/")
            
            # Only accept issue-level links under this comic
            is_issue_link = "/Issue-" in path or (
                comic_slug and 
                path.startswith(f"/Comic/{comic_slug}/") and 
                path != comic_path
            )
            
            if not is_issue_link:
                continue
            
            if link in seen:
                continue
            seen.add(link)
            
            # Clean up title
            title = re.sub(r'<[^>]+>', '', text).strip()
            title = " ".join(title.split())
            
            if not title:
                slug = path.split("/")[-1]
                title = slug.replace("-", " ").replace("_", " ")
                title = " ".join(title.split())
            
            issues.append({"title": title, "url": link})
        
        return issues

    # ---------- Page images (lstImages.push pattern) ----------

    def get_issue_image_urls(self, issue_url):
        """
        Fetch the issue page HTML and extract image URLs from JavaScript.
        The site embeds images using lstImages.push("url") in the HTML.

        Returns a list of image URL strings, one per comic page.
        """
        # Append readType=1 to load all pages on a single page
        separator = "&" if "?" in issue_url else "?"
        all_pages_url = f"{issue_url}{separator}readType=1"
        
        try:
            response = self._http.get(all_pages_url)
            response.raise_for_status()
            html = response.text
        except Exception:
            return []
        
        # Extract image URLs from lstImages.push("url") JavaScript calls
        # Pattern from NOBORU: lstImages\.push\("([^"]*)"\)
        image_urls = []
        pattern = r'lstImages\.push\("([^"]*)"\)'
        matches = re.finditer(pattern, html)
        
        for match in matches:
            img_url = match.group(1)
            # Clean up escaped slashes (JavaScript uses \/ in strings)
            img_url = img_url.replace('\\/', '/')
            if img_url:
                image_urls.append(img_url)
        
        return image_urls

    # ---------- Download ----------

    def _download_single_page(self, img_url, filepath):
        """Download a single image to disk. Returns True on success."""
        if os.path.exists(filepath):
            return True
        try:
            # Add Referer header to avoid 403 errors
            headers = {"Referer": self.base_url + "/"}
            response = self._http.get(img_url, headers=headers)
            response.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(response.content)
            return True
        except Exception:
            return False

    def download_issue(self, issue, output_dir="downloads", on_page_done=None, max_workers=6):
        """
        Download all pages of a single issue.

        Images are downloaded concurrently using a thread pool for maximum
        throughput - the HTTP client and OS I/O are the bottleneck, not CPU,
        so threads are the right tool here.

        Args:
            issue: Dict with "title" and "url" keys.
            output_dir: Base download directory.
            on_page_done: Optional callback(page_num, total_pages) for progress.
            max_workers: Number of concurrent download threads.

        Returns the path to the downloaded issue directory.
        """
        issue_url = issue["url"]
        parsed = urlparse(issue_url)
        path_parts = parsed.path.rstrip("/").split("/")

        # Extract comic title from URL (e.g. "The-Savage-Hulk" from /Comic/The-Savage-Hulk/...)
        comic_title = path_parts[2] if len(path_parts) > 2 else "Unknown"
        comic_title = comic_title.replace("-", " ").replace("_", " ")
        comic_title = " ".join(comic_title.split())

        issue_title = issue["title"].replace("/", "_").replace("\\", "_")

        issue_dir = os.path.join(output_dir, comic_title, issue_title)
        os.makedirs(issue_dir, exist_ok=True)

        # Get all image URLs in one shot (single page load + scroll)
        image_urls = self.get_issue_image_urls(issue_url)
        total = len(image_urls)

        if total == 0:
            return issue_dir

        # Build the work list: (page_number, url, filepath)
        tasks = []
        for page_num, img_url in enumerate(image_urls, start=1):
            if not img_url:
                continue
            ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
            filename = f"{page_num:03d}{ext}"
            filepath = os.path.join(issue_dir, filename)
            tasks.append((page_num, img_url, filepath))

        # Download concurrently
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
        """Release all resources (HTTP client)."""
        if self._http:
            try:
                self._http.close()
            except Exception:
                pass
