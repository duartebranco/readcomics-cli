import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from playwright.sync_api import sync_playwright


class ComicScraper:
    def __init__(self, base_url="https://readcomiconline.li"):
        self.base_url = base_url
        self.scraper = cloudscraper.create_scraper()
        self.browser = None
        self.playwright = None
        self._current_issue_url = None
        self._current_page = None
        self._current_context = None
        self._captured_images = {}

    def _init_playwright(self):
        """Initialize playwright browser"""
        if self.browser is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
        return self.browser

    def search(self, query):
        """Search for comics by title"""
        url = f"{self.base_url}/Search/Comic?keyword={quote_plus(query)}"
        soup = self._get_soup(url)
        results = []
        for a in soup.find_all("a", href=True):
            if "/Comic/" in a["href"]:
                title = a.get_text(strip=True)
                link = urljoin(self.base_url, a["href"].split("?")[0])
                if title and not any(x["url"] == link for x in results):
                    results.append({"title": title, "url": link})
        return results

    def get_issues(self, comic_url):
        """Get all issues for a comic"""
        soup = self._get_soup(comic_url)
        issues = []
        for a in soup.find_all("a", href=True):
            if "/Issue-" in a["href"]:
                link = urljoin(self.base_url, a["href"].split("?")[0])
                if not any(x["url"] == link for x in issues):
                    issues.append({"title": a.get_text(strip=True), "url": link})
        return issues


    def close(self):
        """Clean up resources"""
        try:
            if self._current_page:
                self._current_page.close()
                self._current_page = None
        except Exception:
            pass
        try:
            if self._current_context:
                self._current_context.close()
                self._current_context = None
        except Exception:
            pass
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self.browser = None
        self.playwright = None
        self._current_issue_url = None
        self._captured_images = {}

    def __del__(self):
        """Ensure cleanup on deletion"""
        try:
            self.close()
        except Exception:
            pass
