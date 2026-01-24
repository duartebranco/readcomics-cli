import cloudscraper
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, quote_plus
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class ComicScraper:
    def __init__(self, url):
        self.base_url = url
        # cloudscraper handles Cloudflare IUAM and challenges
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'linux',
                'desktop': True
            }
        )

    def _get_soup(self, url: str) -> BeautifulSoup:
        response = self.scraper.get(url)
        response.raise_for_status()
        # check if we are getting the mobile site or desktop site
        if "Mobile" in response.text:
            logger.info("Detected mobile site response.")
        return BeautifulSoup(response.text, "html.parser")

    def search_comics(self, query: str) -> List[Dict[str, str]]:
        """
        Searches for comics and returns a list of {title, url}.
        """
        search_url = f"{self.base_url}/Search/Comic?keyword={quote_plus(query)}"
        logger.info(f"Searching for comics at: {search_url}")
        soup = self._get_soup(search_url)

        results = []
        # Try a broader selector to catch all links in the main content area
        # Often the mobile site uses different classes like 'list-comic' or just 'a' within specific divs
        links = soup.select("ul.list-comic li a") or \
                soup.select("table.listing tr td a") or \
                soup.select(".list-comic a")

        if not links:
            # Last resort: find all links that look like comic links
            links = [a for a in soup.find_all("a", href=True) if "/Comic/" in a['href']]

        for a in links:
            title = a.get_text(strip=True)
            href = a.get('href', '')

            # Filter out internal links that aren't comic pages
            if "/Comic/" in href and title and not href.endswith("/Comic/"):
                # Handle relative URLs and remove query params
                full_url = urljoin(self.base_url, href.split('?')[0])
                if not any(r['url'] == full_url for r in results):
                    results.append({"title": title, "url": full_url})

        logger.info(f"Found {len(results)} results.")
        return results

    def get_issues(self, comic_url: str) -> List[Dict[str, str]]:
        """Gets all issues for a given comic URL."""
        logger.info(f"Fetching issues for: {comic_url}")
        soup = self._get_soup(comic_url)
        issues = []

        # Try both table listing and the newer list-issue/mobile format
        links = soup.select("table.listing tr td a") or \
                soup.select(".list-issue a") or \
                soup.select("ul.list-issue li a")

        if not links:
            # Fallback for pages that might use different link structures
            links = [a for a in soup.find_all("a", href=True) if "/Issue-" in a['href']]

        for a in links:
            title = a.get_text(strip=True)
            href = a.get('href', '')
            if "/Issue-" in href:
                full_url = urljoin(self.base_url, href.split('?')[0])
                if not any(i['url'] == full_url for i in issues):
                    issues.append({
                        "title": title,
                        "url": full_url
                    })

        # Issues are typically listed newest first on the site
        logger.info(f"Found {len(issues)} issues.")
        return issues


if __name__ == "__main__":
    # # test
    # scraper = ComicScraper("https://readcomiconline.li")
    # results = scraper.search_comics("Sonic")
    # for i, r in enumerate(results[:5]):
    #     print(f"{i}: {r['title']} - {r['url']}")

    # if results:
    #     # first result
    #     issues = scraper.get_issues(results[0]['url'])
    #     for i, issue in enumerate(issues[:5]):
    #         print(f"  {i}: {issue['title']}")
